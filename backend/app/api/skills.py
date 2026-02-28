"""Skills management API endpoints."""

import json
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.logging import get_logger
from app.db.base import get_db
from app.db.models import SkillDefinition
from app.services.skill_registry import skill_registry
from app.skills.validator import skill_code_validator

logger = get_logger(__name__)

router = APIRouter(prefix="/skills", tags=["skills"])

ALLOWED_CATEGORIES = {"research", "code", "data", "creative", "automation"}


# === Request/Response Models ===


class SkillParameterSchema(BaseModel):
    """Skill parameter schema."""

    name: str
    type: str
    description: str
    required: bool
    default: Any = None


class CreateSkillRequest(BaseModel):
    """Request body for creating a new dynamic skill."""

    name: str
    description: str
    category: str
    version: str = "1.0.0"
    tags: list[str] = Field(default_factory=list)
    parameters: list[SkillParameterSchema] = Field(default_factory=list)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    required_tools: list[str] = Field(default_factory=list)
    risk_level: Literal["low", "medium", "high"] | None = None
    source_code: str


class UpdateSkillRequest(BaseModel):
    """Request body for updating an existing dynamic skill."""

    name: str | None = None
    description: str | None = None
    category: str | None = None
    version: str | None = None
    tags: list[str] | None = None
    parameters: list[SkillParameterSchema] | None = None
    output_schema: dict[str, Any] | None = None
    required_tools: list[str] | None = None
    risk_level: Literal["low", "medium", "high"] | None = None
    source_code: str | None = None
    enabled: bool | None = None


class SkillMetadataResponse(BaseModel):
    """Skill metadata response."""

    id: str
    name: str
    version: str
    description: str
    category: str
    parameters: list[SkillParameterSchema]
    output_schema: dict[str, Any]
    required_tools: list[str] = Field(default_factory=list)
    risk_level: Literal["low", "medium", "high"] | None = None
    tags: list[str]
    enabled: bool


class SkillDetailResponse(SkillMetadataResponse):
    """Detailed skill response with source code and metadata."""

    source_code: str | None = None
    is_builtin: bool = False
    author: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class SkillListResponse(BaseModel):
    """Skills list response."""

    skills: list[SkillMetadataResponse]
    count: int
    category: str | None = None


# === Helper ===


def _build_skill_detail(
    skill_meta,
    skill_def: SkillDefinition | None = None,
) -> SkillDetailResponse:
    """Build a SkillDetailResponse from in-memory metadata + optional DB record."""
    params = [
        SkillParameterSchema(
            name=p.name,
            type=p.type,
            description=p.description,
            required=p.required,
            default=p.default,
        )
        for p in skill_meta.parameters
    ]

    is_builtin = (
        skill_def.is_builtin
        if skill_def
        else (skill_meta.id in skill_registry._builtin_skills)
    )
    source_code = None
    if skill_def and not skill_def.is_builtin:
        source_code = skill_def.source_code

    return SkillDetailResponse(
        id=skill_meta.id,
        name=skill_meta.name,
        version=skill_meta.version,
        description=skill_meta.description,
        category=skill_meta.category,
        parameters=params,
        output_schema=skill_meta.output_schema,
        required_tools=getattr(skill_meta, "required_tools", []),
        risk_level=getattr(skill_meta, "risk_level", None),
        tags=skill_meta.tags,
        enabled=skill_meta.enabled,
        source_code=source_code,
        is_builtin=is_builtin,
        author=skill_def.author if skill_def else None,
        created_at=skill_def.created_at.isoformat() if skill_def and skill_def.created_at else None,
        updated_at=skill_def.updated_at.isoformat() if skill_def and skill_def.updated_at else None,
    )


def _enforce_skill_ownership_or_builtin(
    skill_def: SkillDefinition | None,
    current_user_id: str,
    skill_id: str,
) -> None:
    """Enforce that dynamic skills are only accessible by their author.

    Built-in skills are globally readable and manageable (subject to existing
    built-in mutation guards elsewhere).
    """
    if not skill_def:
        # Built-ins may not have DB rows in some environments.
        return
    if skill_def.is_builtin:
        return
    if skill_def.author != current_user_id:
        raise HTTPException(
            status_code=403,
            detail=f"Not authorized to access skill '{skill_id}'",
        )


def _infer_minimum_risk_from_required_tools(required_tools: list[str]) -> Literal["low", "medium", "high"]:
    """Infer minimum risk from referenced tools."""
    from app.agents.hitl.tool_risk import ToolRiskLevel, get_tool_risk_level

    seen_medium = False
    for tool_name in required_tools:
        level = get_tool_risk_level(tool_name)
        if level == ToolRiskLevel.HIGH:
            return "high"
        if level == ToolRiskLevel.MEDIUM:
            seen_medium = True
    return "medium" if seen_medium else "low"


def _validate_skill_tool_metadata(
    required_tools: list[str],
    risk_level: Literal["low", "medium", "high"] | None,
) -> Literal["low", "medium", "high"]:
    """Validate tool metadata and return effective risk level."""
    from app.agents.tools import get_all_tools

    known_tools = {tool.name for tool in get_all_tools()}
    unknown = sorted(set(required_tools) - known_tools)
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown required_tools: {unknown}",
        )

    inferred = _infer_minimum_risk_from_required_tools(required_tools)
    if risk_level is None:
        return inferred

    rank = {"low": 0, "medium": 1, "high": 2}
    if rank[risk_level] < rank[inferred]:
        raise HTTPException(
            status_code=400,
            detail=(
                f"risk_level '{risk_level}' is lower than tool-inferred minimum "
                f"'{inferred}' for required_tools={required_tools}"
            ),
        )
    return risk_level


# === Endpoints ===


@router.get("/load-stats")
async def get_skill_load_stats():
    """Get skill progressive loading statistics.

    Returns a summary of how many skills are at each loading level
    (metadata, instructions, resources).
    """
    return skill_registry.get_load_stats()


@router.get("/", response_model=SkillListResponse)
async def list_skills(
    category: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),
):
    """List all available skills.

    Args:
        category: Optional category filter (research, code, data, creative, automation)
        current_user: Authenticated user

    Returns:
        List of available skills with metadata
    """
    logger.info("list_skills_requested", user_id=current_user.id, category=category)

    try:
        skills = skill_registry.list_skills(category=category)

        skills_response = [
            SkillMetadataResponse(
                id=s.id,
                name=s.name,
                version=s.version,
                description=s.description,
                category=s.category,
                parameters=[
                    SkillParameterSchema(
                        name=p.name,
                        type=p.type,
                        description=p.description,
                        required=p.required,
                        default=p.default,
                    )
                    for p in s.parameters
                ],
                output_schema=s.output_schema,
                required_tools=getattr(s, "required_tools", []),
                risk_level=getattr(s, "risk_level", None),
                tags=s.tags,
                enabled=s.enabled,
            )
            for s in skills
        ]

        return SkillListResponse(
            skills=skills_response,
            count=len(skills_response),
            category=category,
        )

    except Exception as e:
        logger.error("list_skills_failed", error=str(e), user_id=current_user.id)
        raise HTTPException(status_code=500, detail=f"Failed to list skills: {str(e)}")


@router.get("/{skill_id}", response_model=SkillDetailResponse)
async def get_skill(
    skill_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get details about a specific skill.

    Args:
        skill_id: Skill identifier
        current_user: Authenticated user
        db: Database session

    Returns:
        Skill detail with source code for non-builtin skills
    """
    logger.info("get_skill_requested", user_id=current_user.id, skill_id=skill_id)

    skill = skill_registry.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")

    # Try to fetch DB record for extra detail
    result = await db.execute(
        select(SkillDefinition).where(SkillDefinition.id == skill_id)
    )
    skill_def = result.scalar_one_or_none()
    _enforce_skill_ownership_or_builtin(skill_def, current_user.id, skill_id)

    return _build_skill_detail(skill.metadata, skill_def)


@router.post("/", response_model=SkillDetailResponse, status_code=201)
async def create_skill(
    request: CreateSkillRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new dynamic skill.

    Args:
        request: Skill creation request with metadata and source code
        current_user: Authenticated user
        db: Database session

    Returns:
        Created skill metadata
    """
    logger.info("create_skill_requested", user_id=current_user.id, name=request.name)

    # Validate category
    if request.category not in ALLOWED_CATEGORIES:
        allowed = ", ".join(sorted(ALLOWED_CATEGORIES))
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category '{request.category}'. Allowed: {allowed}",
        )

    # Validate source code
    is_valid, error, code_hash = skill_code_validator.validate_and_hash(request.source_code)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid source code: {error}")
    effective_risk = _validate_skill_tool_metadata(request.required_tools, request.risk_level)

    # Generate skill ID from name
    skill_id = request.name.lower().replace(" ", "_").replace("-", "_")

    # Check for duplicate
    existing = skill_registry.get_skill(skill_id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Skill '{skill_id}' already exists")

    try:
        # Build metadata JSON
        metadata_dict = {
            "id": skill_id,
            "name": request.name,
            "version": request.version,
            "description": request.description,
            "category": request.category,
            "parameters": [p.model_dump() for p in request.parameters],
            "output_schema": request.output_schema,
            "required_tools": request.required_tools,
            "risk_level": effective_risk,
            "tags": request.tags,
            "enabled": True,
            "author": current_user.id,
        }

        # Create DB record
        skill_def = SkillDefinition(
            id=skill_id,
            name=request.name,
            version=request.version,
            description=request.description,
            category=request.category,
            module_path="",
            metadata_json=json.dumps(metadata_dict),
            source_code=request.source_code,
            source_code_hash=code_hash,
            enabled=True,
            is_builtin=False,
            author=current_user.id,
        )
        db.add(skill_def)
        await db.commit()
        await db.refresh(skill_def)

        # Load into registry
        await skill_registry._load_dynamic_skill(skill_def)

        # Get loaded skill to return proper metadata
        loaded = skill_registry.get_skill(skill_id)
        if not loaded:
            raise HTTPException(status_code=500, detail="Skill created but failed to load")

        return _build_skill_detail(loaded.metadata, skill_def)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_skill_failed", error=str(e), user_id=current_user.id)
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create skill: {str(e)}")


@router.put("/{skill_id}", response_model=SkillDetailResponse)
async def update_skill(
    skill_id: str,
    request: UpdateSkillRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing dynamic skill.

    Args:
        skill_id: Skill identifier
        request: Fields to update
        current_user: Authenticated user
        db: Database session

    Returns:
        Updated skill detail
    """
    logger.info("update_skill_requested", user_id=current_user.id, skill_id=skill_id)

    # Fetch DB record
    result = await db.execute(
        select(SkillDefinition).where(SkillDefinition.id == skill_id)
    )
    skill_def = result.scalar_one_or_none()
    if not skill_def:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")

    _enforce_skill_ownership_or_builtin(skill_def, current_user.id, skill_id)

    # Guard: reject builtin edits
    if skill_def.is_builtin:
        raise HTTPException(status_code=403, detail="Cannot modify built-in skills")

    # Validate category if provided
    if request.category is not None and request.category not in ALLOWED_CATEGORIES:
        allowed = ", ".join(sorted(ALLOWED_CATEGORIES))
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category '{request.category}'. Allowed: {allowed}",
        )

    # Validate source code if provided
    code_hash = None
    if request.source_code is not None:
        is_valid, error, code_hash = skill_code_validator.validate_and_hash(request.source_code)
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"Invalid source code: {error}")

    try:
        needs_reload = False

        # Apply non-None fields
        if request.name is not None:
            skill_def.name = request.name
        if request.description is not None:
            skill_def.description = request.description
        if request.category is not None:
            skill_def.category = request.category
        if request.version is not None:
            skill_def.version = request.version
        if request.source_code is not None:
            skill_def.source_code = request.source_code
            skill_def.source_code_hash = code_hash
            needs_reload = True
        if request.enabled is not None:
            skill_def.enabled = request.enabled
            needs_reload = True

        # Rebuild metadata_json
        existing_meta = json.loads(skill_def.metadata_json) if skill_def.metadata_json else {}
        existing_meta.update({
            "id": skill_id,
            "name": skill_def.name,
            "version": skill_def.version,
            "description": skill_def.description,
            "category": skill_def.category,
            "enabled": skill_def.enabled,
        })
        if request.tags is not None:
            existing_meta["tags"] = request.tags
        if request.parameters is not None:
            existing_meta["parameters"] = [p.model_dump() for p in request.parameters]
        if request.output_schema is not None:
            existing_meta["output_schema"] = request.output_schema
        if request.required_tools is not None:
            existing_meta["required_tools"] = request.required_tools
        if request.risk_level is not None:
            existing_meta["risk_level"] = request.risk_level

        effective_required_tools = list(existing_meta.get("required_tools", []))
        effective_risk = _validate_skill_tool_metadata(
            required_tools=effective_required_tools,
            risk_level=existing_meta.get("risk_level"),
        )
        existing_meta["risk_level"] = effective_risk

        skill_def.metadata_json = json.dumps(existing_meta)

        await db.commit()
        await db.refresh(skill_def)

        # Hot-reload if needed
        if needs_reload:
            skill_registry.unload_skill(skill_id)
            if skill_def.enabled and skill_def.source_code:
                await skill_registry._load_dynamic_skill(skill_def)

        # Return updated detail
        loaded = skill_registry.get_skill(skill_id)
        if not loaded:
            # Skill may have been disabled
            return SkillDetailResponse(
                id=skill_id,
                name=skill_def.name,
                version=skill_def.version,
                description=skill_def.description,
                category=skill_def.category,
                parameters=[
                    SkillParameterSchema(**p)
                    for p in existing_meta.get("parameters", [])
                ],
                output_schema=existing_meta.get("output_schema", {}),
                required_tools=existing_meta.get("required_tools", []),
                risk_level=existing_meta.get("risk_level"),
                tags=existing_meta.get("tags", []),
                enabled=skill_def.enabled,
                source_code=skill_def.source_code if not skill_def.is_builtin else None,
                is_builtin=skill_def.is_builtin,
                author=skill_def.author,
                created_at=skill_def.created_at.isoformat() if skill_def.created_at else None,
                updated_at=skill_def.updated_at.isoformat() if skill_def.updated_at else None,
            )

        return _build_skill_detail(loaded.metadata, skill_def)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_skill_failed", error=str(e), user_id=current_user.id)
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update skill: {str(e)}")
