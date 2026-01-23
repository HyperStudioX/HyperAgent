"""Stream processor for normalizing and handling agent events."""

import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, Set, Tuple

from app.agents import events as agent_events
from app.core.logging import get_logger
from app.sandbox import get_desktop_sandbox_manager, is_desktop_sandbox_available

logger = get_logger(__name__)

# Streaming configuration - declarative mapping of which nodes should stream tokens
STREAMING_CONFIG = {
    "summarize": True,
    "agent": True,
    "reason": True,  # Chat agent's reason node - stream LLM responses to user
    "write": True,  # Research agent's write node - stream report to user
    "generate": False,  # Code generation - internal step, don't stream to chat
    "synthesize": True,
    "analyze": False,  # Analysis step - internal, only show final summary
    "router": False,
    "tools": False,
    "search_agent": False,
    "search_tools": False,
    # Research subgraph nodes
    "research_prep": False,
    "research_post": False,
    "init_config": False,
    "collect_sources": False,
}

# Browser tools set
BROWSER_TOOLS = {
    "browser_navigate",
    "browser_click",
    "browser_type",
    "browser_screenshot",
    "browser_scroll",
    "browser_press_key",
}

# Mapping of node suffixes to stage information
# Format: (suffix, stage_name, running_desc, completed_desc)
STAGE_DEFINITIONS: List[Tuple[str, str, str, Optional[str]]] = [
    ("plan", "plan", "Planning analysis...", "Analysis planned"),
    ("generate", "generate", "Generating code...", "Code generated"),
    ("execute", "execute", "Executing code...", "Code executed"),
    ("summarize", "summarize", "Summarizing results...", "Results summarized"),
    ("init_config", "config", "Initializing research...", "Research configured"),
    ("search_agent", "search", "Searching for sources...", None),  # Loops
    ("search_tools", "search_tools", "Executing search...", "Search executed"),
    ("collect_sources", "collect", "Collecting sources...", "Sources collected"),
    ("synthesize", "synthesize", "Synthesizing findings...", "Findings synthesized"),
    ("analyze", "analyze", "Analyzing sources...", "Sources analyzed"),
    ("write", "report", "Writing research report...", "Research report complete"),
]

# Browser action descriptions
BROWSER_ACTION_DESCRIPTIONS = {
    "browser_navigate": ("navigate", "Navigating to URL"),
    "browser_click": ("click", "Clicking on element"),
    "browser_type": ("type", "Typing text"),
    "browser_screenshot": ("screenshot", "Taking screenshot"),
    "browser_scroll": ("scroll", "Scrolling page"),
    "browser_press_key": ("key", "Pressing key"),
}


class StreamProcessor:
    """Process and normalize events from the agent graph."""

    def __init__(self, user_id: str | None, task_id: str | None, thread_id: str):
        self.user_id = user_id
        self.task_id = task_id
        self.thread_id = thread_id

        # State tracking
        self.emitted_tool_call_ids: Set[str] = set()
        self.emitted_stage_keys: Set[str] = set()
        self.emitted_image_indices: Set[int] = set()
        self.emitted_interrupt_ids: Set[str] = set()  # Track emitted HITL interrupts
        self.pending_tool_calls: Dict[str, Dict] = {}
        self.pending_tool_calls_by_tool: Dict[str, List[str]] = {}
        self.node_path: List[str] = []
        self.current_content_node: Optional[str] = None
        self.streamed_tokens: bool = False

    def node_matches_streaming(self, node_name: str, node_key: str) -> bool:
        """Check if a node name matches a streaming config key."""
        return node_name == node_key or node_name.endswith(f":{node_key}")

    def path_has_streamable_node(self, node_path_str: str) -> bool:
        """Check if any node in the current path should stream."""
        if not node_path_str:
            return False
        for segment in node_path_str.split("/"):
            for node, enabled in STREAMING_CONFIG.items():
                if enabled and self.node_matches_streaming(segment, node):
                    return True
        return False

    async def process_event(self, event: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """Process a single LangGraph event and yield normalized events."""
        event_type = event.get("event")
        node_name = event.get("name", "")

        if event_type == "on_chain_start":
            async for e in self._handle_chain_start(node_name):
                yield e
        
        elif event_type == "on_chain_end":
            async for e in self._handle_chain_end(node_name, event):
                yield e
        
        elif event_type == "on_chat_model_stream":
            async for e in self._handle_chat_stream(event):
                yield e
        
        elif event_type == "on_tool_start":
            async for e in self._handle_tool_start(event):
                yield e
        
        elif event_type == "on_tool_end":
            async for e in self._handle_tool_end(event):
                yield e
        
        elif event_type == "on_chain_error":
            async for e in self._handle_chain_error(node_name, event):
                yield e

    async def _handle_chain_start(self, node_name: str) -> AsyncGenerator[Dict[str, Any], None]:
        self.node_path.append(node_name)
        
        # Track content-generating nodes
        if any(enabled and self.node_matches_streaming(node_name, node) 
               for node, enabled in STREAMING_CONFIG.items()):
            self.current_content_node = node_name

        # Detect and emit stage running events via configuration
        for suffix, stage_name, desc, _ in STAGE_DEFINITIONS:
            if node_name == suffix or node_name.endswith(f":{suffix}") or node_name.endswith(suffix):
                # Special case for analyze: distinguish research analyze from others if needed
                if stage_name == "analyze" and not any("research" in p for p in self.node_path):
                    continue
                # Special case for write: require research path
                if stage_name == "report" and not any("research" in p for p in self.node_path):
                    continue
                    
                stage_key = f"{stage_name}:running"
                if stage_key not in self.emitted_stage_keys:
                    self.emitted_stage_keys.add(stage_key)
                    yield {
                        "type": "stage", 
                        "name": stage_name, 
                        "description": desc, 
                        "status": "running"
                    }

    async def _handle_chain_end(self, node_name: str, event: Dict) -> AsyncGenerator[Dict[str, Any], None]:
        # Update node path
        if self.node_path and self.node_path[-1] == node_name:
            self.node_path.pop()
        if node_name == self.current_content_node:
            self.current_content_node = None

        # Thinking stage completion
        if node_name == "router" and "thinking" not in self.emitted_stage_keys:
            self.emitted_stage_keys.add("thinking")
            yield {
                "type": "stage",
                "name": "thinking",
                "description": "Request processed",
                "status": "completed",
            }

        # Stage completions via configuration
        for suffix, stage_name, _, completed_desc in STAGE_DEFINITIONS:
            if not completed_desc:
                continue
            if node_name == suffix or node_name.endswith(f":{suffix}") or node_name.endswith(suffix):
                # Same special cases
                if stage_name == "analyze" and not any("research" in p for p in self.node_path):
                    continue
                if stage_name == "report" and not any("research" in p for p in self.node_path):
                    continue

                stage_key = f"{stage_name}:completed"
                if stage_key not in self.emitted_stage_keys:
                    self.emitted_stage_keys.add(stage_key)
                    yield {
                        "type": "stage", 
                        "name": stage_name, 
                        "description": completed_desc, 
                        "status": "completed"
                    }

        # Extract and forward events from subagent output
        event_data = event.get("data") or {}
        output = event_data.get("output") or {}
        if isinstance(output, dict):
            events_list = output.get("events", [])
            if isinstance(events_list, list):
                for e in events_list:
                    if isinstance(e, dict):
                        # Filter/Deduplicate logic
                        if self._should_emit_subevent(e, node_name):
                            yield e

    def _should_emit_subevent(self, e: Dict, node_name: str) -> bool:
        event_type = e.get("type")
        
        # Token deduplication
        is_programmatic_node = any(
            keyword in node_name.lower()
            for keyword in ["present", "image", "summarize"]
        )
        if event_type == "token" and self.streamed_tokens and not is_programmatic_node:
            return False

        # Stage deduplication
        if event_type == "stage":
            stage_key = f"{e.get('name')}:{e.get('status')}"
            if stage_key in self.emitted_stage_keys:
                return False
            self.emitted_stage_keys.add(stage_key)

        # Tool call deduplication
        if event_type == "tool_call":
            tool_id = e.get("id")
            if tool_id and tool_id in self.emitted_tool_call_ids:
                return False
            if tool_id:
                self.emitted_tool_call_ids.add(tool_id)

        # Tool result deduplication
        if event_type == "tool_result":
            tool_id = e.get("id")
            result_key = f"result:{tool_id}"
            if tool_id and result_key in self.emitted_tool_call_ids:
                return False
            if tool_id:
                self.emitted_tool_call_ids.add(result_key)

        # Image deduplication
        if event_type == "image":
            image_index = e.get("index", 0)
            if image_index in self.emitted_image_indices:
                return False
            self.emitted_image_indices.add(image_index)
            logger.info("yielding_image_event", index=image_index, node_name=node_name)

        # Interrupt deduplication (HITL events)
        if event_type == "interrupt":
            interrupt_id = e.get("interrupt_id")
            if interrupt_id and interrupt_id in self.emitted_interrupt_ids:
                logger.info(
                    "interrupt_deduplicated",
                    interrupt_id=interrupt_id,
                    message=e.get("message", "")[:50],
                )
                return False
            if interrupt_id:
                self.emitted_interrupt_ids.add(interrupt_id)
                logger.info(
                    "interrupt_emitting",
                    interrupt_id=interrupt_id,
                    message=e.get("message", "")[:50],
                )

        return True

    async def _handle_chat_stream(self, event: Dict) -> AsyncGenerator[Dict[str, Any], None]:
        node_path_str = "/".join(self.node_path)
        chunk = (event.get("data") or {}).get("chunk")
        
        # Tool call chunks
        if chunk and getattr(chunk, "tool_calls", None):
            for tool_call in chunk.tool_calls:
                if not tool_call or not isinstance(tool_call, dict):
                    continue
                func = tool_call.get("function") if isinstance(tool_call.get("function"), dict) else None
                tool_name = tool_call.get("name") or tool_call.get("tool") or (func.get("name") if func else None)
                
                if not tool_name:
                    continue
                    
                tool_id = tool_call.get("id") or tool_call.get("tool_call_id") or str(uuid.uuid4())
                
                if tool_id in self.emitted_tool_call_ids:
                    continue
                    
                self.emitted_tool_call_ids.add(tool_id)
                tool_args = tool_call.get("args") or {}
                
                self.pending_tool_calls[tool_id] = {
                    "tool": tool_name,
                    "args": tool_args,
                }
                self.pending_tool_calls_by_tool.setdefault(tool_name, []).append(tool_id)
                
                yield {
                    "type": "tool_call",
                    "tool": tool_name,
                    "args": tool_args,
                    "id": tool_id,
                }

        # Streaming content tokens
        if self.path_has_streamable_node(node_path_str):
            chunk = (event.get("data") or {}).get("chunk")
            if chunk and hasattr(chunk, "content") and chunk.content:
                from app.ai.llm import extract_text_from_content
                content = extract_text_from_content(chunk.content)
                if content:
                    self.streamed_tokens = True
                    yield {"type": "token", "content": content}

    async def _handle_tool_start(self, event: Dict) -> AsyncGenerator[Dict[str, Any], None]:
        run_id = event.get("run_id", "")
        tool_name = event.get("name", "")
        tool_input = (event.get("data") or {}).get("input") or {}

        # Handle Browser Stream (Side Effect)
        if tool_name in BROWSER_TOOLS:
            async for e in self._emit_browser_stream(tool_input):
                 yield e

        # Track tool call
        tool_call_id = None
        if isinstance(tool_input, dict):
            tool_call_id = tool_input.get("tool_call_id")
        
        if run_id and not tool_call_id:
            tool_call_id = str(run_id)

        if tool_name and tool_call_id and tool_call_id not in self.emitted_tool_call_ids:
            self.emitted_tool_call_ids.add(tool_call_id)
            self.pending_tool_calls[tool_call_id] = {
                "tool": tool_name,
                "run_id": run_id,
            }
            self.pending_tool_calls_by_tool.setdefault(tool_name, []).append(tool_call_id)
            
            yield {
                "type": "tool_call",
                "tool": tool_name,
                "args": tool_input if isinstance(tool_input, dict) else {},
                "id": tool_call_id,
            }

        # Browser action events
        if tool_name in BROWSER_ACTION_DESCRIPTIONS:
            action, desc = BROWSER_ACTION_DESCRIPTIONS[tool_name]
            
            # Extract target from specific keys based on action
            target = ""
            if isinstance(tool_input, dict):
                if action == "navigate":
                    target = tool_input.get("url", "")
                elif action == "click":
                    target = f"({tool_input.get('x', '?')}, {tool_input.get('y', '?')})"
                elif action == "type":
                    target = tool_input.get("text", "")[:50]
                elif action == "scroll":
                    target = tool_input.get("direction", "down")
                elif action == "key":
                    target = tool_input.get("key", "")

            yield agent_events.browser_action(
                action=action,
                description=desc,
                target=target,
                status="running",
            )

    async def _emit_browser_stream(self, tool_input: Any) -> AsyncGenerator[Dict[str, Any], None]:
        if not is_desktop_sandbox_available():
            return

        uid = tool_input.get("user_id") if isinstance(tool_input, dict) else None
        tid = tool_input.get("task_id") if isinstance(tool_input, dict) else None
        uid = uid if uid is not None else self.user_id
        tid = tid if tid is not None else self.task_id

        try:
            manager = get_desktop_sandbox_manager()
            session = await manager.get_or_create_sandbox(
                user_id=uid,
                task_id=tid,
                launch_browser=True,
            )
            stream_url, auth_key = await manager.ensure_stream_ready(session)
            yield agent_events.browser_stream(
                stream_url=stream_url,
                sandbox_id=session.sandbox_id,
                auth_key=auth_key,
            )
        except Exception as e:
            logger.warning("browser_stream_emit_failed", error=str(e))

    async def _handle_tool_end(self, event: Dict) -> AsyncGenerator[Dict[str, Any], None]:
        run_id = event.get("run_id", "")
        tool_name = event.get("name", "")
        output = (event.get("data") or {}).get("output", "")

        # Browser action completion
        if tool_name in BROWSER_TOOLS:
            action = BROWSER_ACTION_DESCRIPTIONS.get(tool_name, (tool_name,))[0]
            readable_name = tool_name.replace('browser_', '').replace('_', ' ').title()
            yield agent_events.browser_action(
                action=action,
                description=f"{readable_name} completed",
                status="completed",
            )

        # Resolve tool call ID
        tool_call_id = self._resolve_tool_call_id(run_id, tool_name)
        
        # Emit tool result
        content = str(output)[:500] if output else ""
        yield {
            "type": "tool_result",
            "tool": tool_name,
            "content": content,
            "id": tool_call_id,
        }

        # Cleanup pending
        self.pending_tool_calls.pop(tool_call_id, None)
        if tool_name in self.pending_tool_calls_by_tool:
            try:
                self.pending_tool_calls_by_tool[tool_name].remove(tool_call_id)
                if not self.pending_tool_calls_by_tool[tool_name]:
                    self.pending_tool_calls_by_tool.pop(tool_name, None)
            except ValueError:
                pass

    def _resolve_tool_call_id(self, run_id: str, tool_name: str) -> str:
        tool_call_id = None
        
        # Try finding by run_id
        if run_id:
            for tid, info in self.pending_tool_calls.items():
                if info.get("run_id") == run_id:
                    tool_call_id = tid
                    break
        
        # Try popping from queue by tool name
        if not tool_call_id and tool_name:
            tool_queue = self.pending_tool_calls_by_tool.get(tool_name) or []
            if tool_queue:
                tool_call_id = tool_queue.pop(0)

        return tool_call_id or str(run_id) if run_id else str(uuid.uuid4())

    async def _handle_chain_error(self, node_name: str, event: Dict) -> AsyncGenerator[Dict[str, Any], None]:
        error = (event.get("data") or {}).get("error")
        if error:
            yield {
                "type": "error",
                "error": str(error),
                "node": node_name,
            }
            logger.error(
                "subagent_error",
                node=node_name,
                error=str(error),
                thread_id=self.thread_id,
            )
