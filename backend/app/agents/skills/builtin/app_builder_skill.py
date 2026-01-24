"""App Builder Skill for creating and running web applications.

This skill orchestrates the full workflow of building and deploying
web applications in an isolated sandbox environment.
"""

from typing import Any

from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from app.agents import events as agent_events
from app.agents.skills.skill_base import Skill, SkillMetadata, SkillParameter, SkillState
from app.ai.llm import LLMService
from app.ai.model_tiers import ModelTier
from app.core.logging import get_logger
from app.sandbox.app_sandbox_manager import (
    APP_TEMPLATES,
    get_app_sandbox_manager,
)

logger = get_logger(__name__)
llm_service = LLMService()


class AppPlan(BaseModel):
    """Plan for building an application."""

    template: str = Field(
        description="Template to use (react, nextjs, vue, express, fastapi, flask, static)"
    )
    features: list[str] = Field(description="List of features to implement")
    files: list[dict[str, str]] = Field(
        description="List of files to create with path and description"
    )
    packages: list[str] = Field(default=[], description="Additional packages to install")
    explanation: str = Field(description="Brief explanation of the app architecture")


class FileContent(BaseModel):
    """Generated file content."""

    path: str = Field(description="File path relative to project root")
    content: str = Field(description="Complete file content")
    description: str = Field(description="What this file does")


class AppBuilderState(SkillState):
    """State for app builder skill execution."""

    plan: dict[str, Any] | None
    generated_files: list[dict[str, Any]]
    preview_url: str | None
    build_errors: list[str]
    current_step: str
    # Events to emit during streaming
    pending_events: list[dict[str, Any]]


class AppBuilderSkill(Skill):
    """Builds and runs web applications from natural language descriptions."""

    metadata = SkillMetadata(
        id="app_builder",
        name="App Builder",
        version="1.0.0",
        description="Builds and runs web applications from descriptions. Supports React, Next.js, Vue, Express, FastAPI, Flask, and static sites. Creates a live preview URL.",
        category="development",
        parameters=[
            SkillParameter(
                name="description",
                type="string",
                description="Description of the app to build (e.g., 'A todo list app with dark mode')",
                required=True,
            ),
            SkillParameter(
                name="template",
                type="string",
                description="Template to use: react, react-ts, nextjs, vue, express, fastapi, flask, static. If not specified, the skill will choose based on the description.",
                required=False,
                default=None,
            ),
            SkillParameter(
                name="features",
                type="array",
                description="List of specific features to include",
                required=False,
                default=[],
            ),
        ],
        output_schema={
            "type": "object",
            "properties": {
                "preview_url": {
                    "type": "string",
                    "description": "Live preview URL where the app can be viewed",
                },
                "files_created": {
                    "type": "array",
                    "description": "List of files created",
                },
                "template": {
                    "type": "string",
                    "description": "Template used",
                },
                "message": {
                    "type": "string",
                    "description": "Summary of what was built",
                },
            },
        },
        required_tools=[
            "create_app_project",
            "app_write_file",
            "app_install_packages",
            "app_start_server",
        ],
        max_execution_time_seconds=600,  # 10 minutes for full build
        max_iterations=20,
        tags=["app", "web", "development", "react", "nextjs", "vue", "express", "fastapi"],
    )

    def create_graph(self) -> StateGraph:
        """Create the LangGraph subgraph for app building."""
        graph = StateGraph(AppBuilderState)

        async def plan_app(state: AppBuilderState) -> dict:
            """Plan the application structure and files."""
            description = state["input_params"]["description"]
            requested_template = state["input_params"].get("template")
            requested_features = state["input_params"].get("features", [])

            # Emit stage event for planning
            pending_events = state.get("pending_events", [])
            pending_events.append(
                agent_events.stage(
                    name="plan",
                    description="Planning app structure and architecture",
                    status="running",
                )
            )

            logger.info(
                "app_builder_planning",
                description=description[:100],
                template=requested_template,
            )

            try:
                # Build prompt for planning
                templates_info = "\n".join(
                    [
                        f"- {name}: {config['name']} (port {config['port']})"
                        for name, config in APP_TEMPLATES.items()
                    ]
                )

                features_hint = ""
                if requested_features:
                    features_hint = f"\n\nRequested features: {', '.join(requested_features)}"

                template_hint = ""
                if requested_template:
                    template_hint = f"\n\nUser requested template: {requested_template}"

                prompt = f"""Plan a web application based on this description:

{description}{features_hint}{template_hint}

Available templates:
{templates_info}

Create a plan that includes:
1. The best template to use (considering the app type and requirements)
2. List of key features to implement
3. List of files to create (path and brief description)
4. Any additional packages needed

Be practical and create a working app, not just boilerplate. Focus on the core functionality described."""

                # Get LLM for planning
                llm = llm_service.get_llm_for_tier(ModelTier.PRO)
                structured_llm = llm.with_structured_output(AppPlan)

                plan: AppPlan = await structured_llm.ainvoke(prompt)

                logger.info(
                    "app_builder_planned",
                    template=plan.template,
                    file_count=len(plan.files),
                    package_count=len(plan.packages),
                )

                # Mark planning as complete
                pending_events.append(
                    agent_events.stage(
                        name="plan",
                        description=f"Planned {plan.template} app with {len(plan.files)} files",
                        status="completed",
                    )
                )

                return {
                    "plan": plan.model_dump(),
                    "current_step": "scaffold",
                    "iterations": state.get("iterations", 0) + 1,
                    "pending_events": pending_events,
                }

            except Exception as e:
                logger.error("app_builder_plan_failed", error=str(e))
                pending_events.append(
                    agent_events.stage(
                        name="plan",
                        description="Failed to plan app structure",
                        status="failed",
                    )
                )
                return {
                    "error": f"Failed to plan app: {str(e)}",
                    "current_step": "error",
                    "iterations": state.get("iterations", 0) + 1,
                    "pending_events": pending_events,
                }

        async def scaffold_project(state: AppBuilderState) -> dict:
            """Scaffold the project using the selected template."""
            plan = state.get("plan", {})
            template = plan.get("template", "react")
            user_id = state.get("user_id")
            task_id = state.get("task_id")

            # Emit stage event for scaffolding
            pending_events = state.get("pending_events", [])
            pending_events.append(
                agent_events.stage(
                    name="scaffold",
                    description=f"Creating {template} project structure",
                    status="running",
                )
            )

            logger.info(
                "app_builder_scaffolding",
                template=template,
            )

            try:
                manager = get_app_sandbox_manager()

                # Create sandbox and scaffold
                session = await manager.get_or_create_sandbox(
                    user_id=user_id,
                    task_id=task_id,
                    template=template,
                )

                result = await manager.scaffold_project(session, template)

                if not result["success"]:
                    pending_events.append(
                        agent_events.stage(
                            name="scaffold",
                            description="Failed to create project structure",
                            status="failed",
                        )
                    )
                    return {
                        "error": f"Scaffold failed: {result.get('error', 'Unknown error')}",
                        "current_step": "error",
                        "iterations": state.get("iterations", 0) + 1,
                        "pending_events": pending_events,
                    }

                # Install additional packages if needed
                packages = plan.get("packages", [])
                if packages:
                    pkg_manager = "pip" if template in ["fastapi", "flask"] else "npm"
                    await manager.install_dependencies(session, packages, pkg_manager)

                pending_events.append(
                    agent_events.stage(
                        name="scaffold",
                        description=f"Created {template} project with dependencies",
                        status="completed",
                    )
                )

                return {
                    "current_step": "generate_files",
                    "iterations": state.get("iterations", 0) + 1,
                    "pending_events": pending_events,
                }

            except Exception as e:
                logger.error("app_builder_scaffold_failed", error=str(e))
                pending_events.append(
                    agent_events.stage(
                        name="scaffold",
                        description="Failed to scaffold project",
                        status="failed",
                    )
                )
                return {
                    "error": f"Failed to scaffold: {str(e)}",
                    "current_step": "error",
                    "iterations": state.get("iterations", 0) + 1,
                    "pending_events": pending_events,
                }

        async def generate_files(state: AppBuilderState) -> dict:
            """Generate the application files."""
            plan = state.get("plan", {})
            description = state["input_params"]["description"]
            template = plan.get("template", "react")
            files_to_create = plan.get("files", [])
            user_id = state.get("user_id")
            task_id = state.get("task_id")

            # Emit stage event for file generation
            pending_events = state.get("pending_events", [])
            pending_events.append(
                agent_events.stage(
                    name="generate",
                    description=f"Generating {len(files_to_create)} application files",
                    status="running",
                )
            )

            logger.info(
                "app_builder_generating_files",
                file_count=len(files_to_create),
            )

            try:
                manager = get_app_sandbox_manager()
                session = await manager.get_session(user_id=user_id, task_id=task_id)

                if not session:
                    pending_events.append(
                        agent_events.stage(
                            name="generate",
                            description="No active sandbox session",
                            status="failed",
                        )
                    )
                    return {
                        "error": "No active sandbox session",
                        "current_step": "error",
                        "iterations": state.get("iterations", 0) + 1,
                        "pending_events": pending_events,
                    }

                generated_files = []
                build_errors = []

                # Generate each file using LLM
                llm = llm_service.get_llm_for_tier(ModelTier.PRO)
                structured_llm = llm.with_structured_output(FileContent)

                for file_spec in files_to_create:
                    file_path = file_spec.get("path", "")
                    file_desc = file_spec.get("description", "")

                    if not file_path:
                        continue

                    # Generate file content
                    prompt = f"""Generate the complete content for this file in a {template} project:

App Description: {description}

File: {file_path}
Purpose: {file_desc}

Project Structure:
{chr(10).join([f"- {f.get('path')}: {f.get('description')}" for f in files_to_create])}

Generate production-quality, working code. Include all necessary imports.
For React: use functional components and hooks.
For Next.js: use App Router conventions.
For Vue: use Composition API.
For Express/FastAPI/Flask: include proper error handling.

The code should be complete and immediately runnable."""

                    try:
                        file_content: FileContent = await structured_llm.ainvoke(prompt)

                        # Write the file
                        result = await manager.write_file(
                            session,
                            file_content.path,
                            file_content.content,
                        )

                        if result["success"]:
                            generated_files.append(
                                {
                                    "path": file_content.path,
                                    "description": file_content.description,
                                }
                            )
                            logger.info(
                                "app_builder_file_written",
                                path=file_content.path,
                            )
                        else:
                            build_errors.append(
                                f"Failed to write {file_path}: {result.get('error')}"
                            )

                    except Exception as e:
                        build_errors.append(f"Failed to generate {file_path}: {str(e)}")
                        logger.warning(
                            "app_builder_file_generation_failed",
                            path=file_path,
                            error=str(e),
                        )

                pending_events.append(
                    agent_events.stage(
                        name="generate",
                        description=f"Generated {len(generated_files)} files",
                        status="completed" if not build_errors else "running",
                    )
                )

                return {
                    "generated_files": generated_files,
                    "build_errors": build_errors,
                    "current_step": "start_server",
                    "iterations": state.get("iterations", 0) + 1,
                    "pending_events": pending_events,
                }

            except Exception as e:
                logger.error("app_builder_generate_files_failed", error=str(e))
                pending_events.append(
                    agent_events.stage(
                        name="generate",
                        description="Failed to generate files",
                        status="failed",
                    )
                )
                return {
                    "error": f"Failed to generate files: {str(e)}",
                    "current_step": "error",
                    "iterations": state.get("iterations", 0) + 1,
                    "pending_events": pending_events,
                }

        async def start_server(state: AppBuilderState) -> dict:
            """Start the development server and get preview URL."""
            user_id = state.get("user_id")
            task_id = state.get("task_id")

            # Emit stage event for server start
            pending_events = state.get("pending_events", [])
            pending_events.append(
                agent_events.stage(
                    name="server",
                    description="Starting development server",
                    status="running",
                )
            )

            logger.info("app_builder_starting_server")

            try:
                manager = get_app_sandbox_manager()
                session = await manager.get_session(user_id=user_id, task_id=task_id)

                if not session:
                    pending_events.append(
                        agent_events.stage(
                            name="server",
                            description="No active sandbox session",
                            status="failed",
                        )
                    )
                    return {
                        "error": "No active sandbox session",
                        "current_step": "error",
                        "iterations": state.get("iterations", 0) + 1,
                        "pending_events": pending_events,
                    }

                # Start the dev server
                result = await manager.start_dev_server(session)

                if result["success"]:
                    pending_events.append(
                        agent_events.stage(
                            name="server",
                            description="Server started successfully",
                            status="completed",
                        )
                    )
                    return {
                        "preview_url": result["preview_url"],
                        "current_step": "complete",
                        "iterations": state.get("iterations", 0) + 1,
                        "pending_events": pending_events,
                    }
                else:
                    pending_events.append(
                        agent_events.stage(
                            name="server",
                            description="Failed to start server",
                            status="failed",
                        )
                    )
                    return {
                        "build_errors": state.get("build_errors", [])
                        + [result.get("error", "Server start failed")],
                        "current_step": "error",
                        "iterations": state.get("iterations", 0) + 1,
                        "pending_events": pending_events,
                    }

            except Exception as e:
                logger.error("app_builder_start_server_failed", error=str(e))
                pending_events.append(
                    agent_events.stage(
                        name="server",
                        description="Failed to start server",
                        status="failed",
                    )
                )
                return {
                    "error": f"Failed to start server: {str(e)}",
                    "current_step": "error",
                    "iterations": state.get("iterations", 0) + 1,
                    "pending_events": pending_events,
                }

        async def finalize(state: AppBuilderState) -> dict:
            """Finalize the build and prepare output."""
            plan = state.get("plan", {})
            generated_files = state.get("generated_files", [])
            preview_url = state.get("preview_url")
            build_errors = state.get("build_errors", [])

            # Emit stage event for finalization
            pending_events = state.get("pending_events", [])
            pending_events.append(
                agent_events.stage(
                    name="finalize",
                    description="Finalizing app build",
                    status="running",
                )
            )

            logger.info(
                "app_builder_finalizing",
                preview_url=preview_url,
                files_count=len(generated_files),
                errors_count=len(build_errors),
            )

            # Prepare output
            if preview_url:
                output = {
                    "success": True,
                    "preview_url": preview_url,
                    "template": plan.get("template", "unknown"),
                    "files_created": [f["path"] for f in generated_files],
                    "message": f"App built successfully! View it at: {preview_url}",
                }

                if build_errors:
                    output["warnings"] = build_errors

                pending_events.append(
                    agent_events.stage(
                        name="finalize",
                        description="App ready for preview",
                        status="completed",
                    )
                )

            else:
                output = {
                    "success": False,
                    "template": plan.get("template", "unknown"),
                    "files_created": [f["path"] for f in generated_files],
                    "errors": build_errors or ["Unknown error occurred"],
                    "message": "App build encountered errors. Check the errors list for details.",
                }

                pending_events.append(
                    agent_events.stage(
                        name="finalize",
                        description="Build completed with errors",
                        status="failed",
                    )
                )

            return {
                "output": output,
                "current_step": "done",
                "iterations": state.get("iterations", 0) + 1,
                "pending_events": pending_events,
            }

        def route_step(state: AppBuilderState) -> str:
            """Route to the next step based on current state."""
            current = state.get("current_step", "plan")
            error = state.get("error")

            if error:
                return "finalize"

            step_routing = {
                "plan": "scaffold",
                "scaffold": "generate_files",
                "generate_files": "start_server",
                "start_server": "finalize",
                "complete": "finalize",
                "error": "finalize",
            }

            return step_routing.get(current, "finalize")

        # Build the graph
        graph.add_node("plan", plan_app)
        graph.add_node("scaffold", scaffold_project)
        graph.add_node("generate_files", generate_files)
        graph.add_node("start_server", start_server)
        graph.add_node("finalize", finalize)

        # Set entry point
        graph.set_entry_point("plan")

        # Add conditional edges based on step
        graph.add_conditional_edges(
            "plan",
            route_step,
            {
                "scaffold": "scaffold",
                "finalize": "finalize",
            },
        )
        graph.add_conditional_edges(
            "scaffold",
            route_step,
            {
                "generate_files": "generate_files",
                "finalize": "finalize",
            },
        )
        graph.add_conditional_edges(
            "generate_files",
            route_step,
            {
                "start_server": "start_server",
                "finalize": "finalize",
            },
        )
        graph.add_conditional_edges(
            "start_server",
            route_step,
            {
                "finalize": "finalize",
            },
        )
        graph.add_edge("finalize", END)

        return graph.compile()
