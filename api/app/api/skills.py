"""Skills management API endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth import CurrentUser, get_current_user
from app.core.logging import get_logger
from app.services.skill_registry import skill_registry

logger = get_logger(__name__)

router = APIRouter(prefix="/skills", tags=["skills"])


# === Request/Response Models ===


class SkillParameterSchema(BaseModel):
    """Skill parameter schema."""

    name: str
    type: str
    description: str
    required: bool
    default: Any = None


class SkillMetadataResponse(BaseModel):
    """Skill metadata response."""

    id: str
    name: str
    version: str
    description: str
    category: str
    parameters: list[SkillParameterSchema]
    output_schema: dict[str, Any]
    tags: list[str]
    enabled: bool


class SkillListResponse(BaseModel):
    """Skills list response."""

    skills: list[SkillMetadataResponse]
    count: int
    category: str | None = None


# === Endpoints ===


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


@router.get("/{skill_id}", response_model=SkillMetadataResponse)
async def get_skill(
    skill_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get details about a specific skill.

    Args:
        skill_id: Skill identifier
        current_user: Authenticated user

    Returns:
        Skill metadata
    """
    logger.info("get_skill_requested", user_id=current_user.id, skill_id=skill_id)

    skill = skill_registry.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")

    return SkillMetadataResponse(
        id=skill.metadata.id,
        name=skill.metadata.name,
        version=skill.metadata.version,
        description=skill.metadata.description,
        category=skill.metadata.category,
        parameters=[
            SkillParameterSchema(
                name=p.name,
                type=p.type,
                description=p.description,
                required=p.required,
                default=p.default,
            )
            for p in skill.metadata.parameters
        ],
        output_schema=skill.metadata.output_schema,
        tags=skill.metadata.tags,
        enabled=skill.metadata.enabled,
    )
