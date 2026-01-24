"""Human-in-the-Loop (HITL) module for agent interrupts and approvals.

This module provides:
- InterruptManager: Manages interrupt lifecycle using Redis pub/sub
- Tool risk registry: Defines high-risk tools requiring approval
- Interrupt helpers: Create and process interrupt events
"""

from app.agents.hitl.interrupt_manager import InterruptManager
from app.agents.hitl.tool_risk import (
    HIGH_RISK_TOOLS,
    MEDIUM_RISK_TOOLS,
    get_tool_risk_level,
    requires_approval,
)

__all__ = [
    "InterruptManager",
    "HIGH_RISK_TOOLS",
    "MEDIUM_RISK_TOOLS",
    "get_tool_risk_level",
    "requires_approval",
]
