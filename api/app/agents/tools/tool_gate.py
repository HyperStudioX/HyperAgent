"""Heuristics for deciding when to enable agent tools.

This module provides a configurable, scored approach to tool enablement
using pattern matching, semantic analysis, and context-aware rules.

Key features:
- Categorized trigger patterns with confidence scores
- Negative patterns to reduce false positives
- Semantic intent detection (question words, action verbs)
- Context-aware rules (query length, structure)
- Configurable thresholds
- Detailed logging for debugging
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from typing import Callable

from app.core.logging import get_logger

logger = get_logger(__name__)


class ToolCategory(str, Enum):
    """Categories of tools that can be enabled."""

    SEARCH = "search"
    IMAGE_GENERATION = "image_generation"
    IMAGE_ANALYSIS = "image_analysis"
    BROWSER = "browser"
    CODE_EXECUTION = "code_execution"


@dataclass
class TriggerPattern:
    """A pattern that triggers tool enablement.

    Attributes:
        pattern: The text pattern to match
        category: Which tool category this triggers
        score: Confidence score when matched (0.0 to 1.0)
        requires_boundary: Whether to use word boundaries
        is_negative: If True, this pattern reduces the score
    """

    pattern: str
    category: ToolCategory
    score: float = 0.8
    requires_boundary: bool = False
    is_negative: bool = False

    def __post_init__(self):
        """Compile the regex pattern."""
        if self.requires_boundary:
            self._compiled = re.compile(
                r'\b' + re.escape(self.pattern) + r'\b',
                re.IGNORECASE
            )
        else:
            self._compiled = re.compile(re.escape(self.pattern), re.IGNORECASE)

    def matches(self, text: str) -> bool:
        """Check if this pattern matches the text."""
        return bool(self._compiled.search(text))


@dataclass
class SemanticRule:
    """A semantic rule for intent detection.

    Attributes:
        name: Rule identifier for logging
        categories: Tool categories this rule applies to
        check: Function that returns (matches, score) tuple
    """

    name: str
    categories: list[ToolCategory]
    check: Callable[[str], tuple[bool, float]]


@dataclass
class ToolEnablementResult:
    """Result of tool enablement check.

    Attributes:
        should_enable: Whether tools should be enabled
        confidence: Confidence score (0.0 to 1.0)
        matched_patterns: List of patterns that matched
        matched_rules: List of semantic rules that matched
        category_scores: Per-category confidence scores
    """

    should_enable: bool
    confidence: float
    matched_patterns: list[str] = field(default_factory=list)
    matched_rules: list[str] = field(default_factory=list)
    category_scores: dict[ToolCategory, float] = field(default_factory=dict)


# =============================================================================
# Pattern Definitions
# =============================================================================

# Search trigger patterns with confidence scores
SEARCH_PATTERNS = [
    # Explicit search requests (high confidence)
    TriggerPattern("search the web", ToolCategory.SEARCH, 1.0),
    TriggerPattern("search for", ToolCategory.SEARCH, 0.9),
    TriggerPattern("search online", ToolCategory.SEARCH, 1.0),
    TriggerPattern("web search", ToolCategory.SEARCH, 1.0),
    TriggerPattern("google", ToolCategory.SEARCH, 0.9, requires_boundary=True),
    TriggerPattern("look up", ToolCategory.SEARCH, 0.85),
    TriggerPattern("find out", ToolCategory.SEARCH, 0.7),
    TriggerPattern("find information", ToolCategory.SEARCH, 0.9),
    TriggerPattern("find sources", ToolCategory.SEARCH, 0.9),

    # Browse/navigation (medium confidence)
    TriggerPattern("browse", ToolCategory.SEARCH, 0.7, requires_boundary=True),
    TriggerPattern("navigate to", ToolCategory.SEARCH, 0.6),

    # Research/citation requests (high confidence)
    TriggerPattern("research", ToolCategory.SEARCH, 0.75, requires_boundary=True),
    TriggerPattern("citations", ToolCategory.SEARCH, 0.85, requires_boundary=True),
    TriggerPattern("references", ToolCategory.SEARCH, 0.7, requires_boundary=True),
    TriggerPattern("sources for", ToolCategory.SEARCH, 0.85),
    TriggerPattern("cite", ToolCategory.SEARCH, 0.7, requires_boundary=True),

    # Time-sensitive queries (high confidence)
    TriggerPattern("latest", ToolCategory.SEARCH, 0.8, requires_boundary=True),
    TriggerPattern("recent", ToolCategory.SEARCH, 0.7, requires_boundary=True),
    TriggerPattern("current", ToolCategory.SEARCH, 0.6, requires_boundary=True),
    TriggerPattern("today's", ToolCategory.SEARCH, 0.85),
    TriggerPattern("yesterday's", ToolCategory.SEARCH, 0.85),
    TriggerPattern("this week", ToolCategory.SEARCH, 0.8),
    TriggerPattern("this month", ToolCategory.SEARCH, 0.75),
    TriggerPattern("in 2024", ToolCategory.SEARCH, 0.7),
    TriggerPattern("in 2025", ToolCategory.SEARCH, 0.7),
    TriggerPattern("in 2026", ToolCategory.SEARCH, 0.7),

    # News queries (high confidence)
    TriggerPattern("news about", ToolCategory.SEARCH, 0.95),
    TriggerPattern("latest news", ToolCategory.SEARCH, 0.95),
    TriggerPattern("recent news", ToolCategory.SEARCH, 0.95),
    TriggerPattern("breaking news", ToolCategory.SEARCH, 0.95),
    TriggerPattern("headlines", ToolCategory.SEARCH, 0.85, requires_boundary=True),

    # Real-time data queries (high confidence)
    TriggerPattern("current price", ToolCategory.SEARCH, 0.95),
    TriggerPattern("stock price", ToolCategory.SEARCH, 0.95),
    TriggerPattern("exchange rate", ToolCategory.SEARCH, 0.9),
    TriggerPattern("weather", ToolCategory.SEARCH, 0.9, requires_boundary=True),
    TriggerPattern("forecast", ToolCategory.SEARCH, 0.85, requires_boundary=True),
    TriggerPattern("score", ToolCategory.SEARCH, 0.5, requires_boundary=True),
    TriggerPattern("standings", ToolCategory.SEARCH, 0.8, requires_boundary=True),

    # Product/release queries (medium confidence)
    TriggerPattern("release date", ToolCategory.SEARCH, 0.85),
    TriggerPattern("release notes", ToolCategory.SEARCH, 0.8),
    TriggerPattern("when will", ToolCategory.SEARCH, 0.6),
    TriggerPattern("when does", ToolCategory.SEARCH, 0.6),
    TriggerPattern("when did", ToolCategory.SEARCH, 0.5),
    TriggerPattern("how much does", ToolCategory.SEARCH, 0.6),
    TriggerPattern("where can i buy", ToolCategory.SEARCH, 0.8),
    TriggerPattern("where to buy", ToolCategory.SEARCH, 0.8),

    # Comparison/review queries (medium confidence)
    TriggerPattern("compare", ToolCategory.SEARCH, 0.6, requires_boundary=True),
    TriggerPattern("vs", ToolCategory.SEARCH, 0.5, requires_boundary=True),
    TriggerPattern("versus", ToolCategory.SEARCH, 0.5, requires_boundary=True),
    TriggerPattern("reviews of", ToolCategory.SEARCH, 0.8),
    TriggerPattern("best", ToolCategory.SEARCH, 0.5, requires_boundary=True),
    TriggerPattern("top 10", ToolCategory.SEARCH, 0.7),
    TriggerPattern("top 5", ToolCategory.SEARCH, 0.7),

    # Chinese triggers
    TriggerPattern("搜索", ToolCategory.SEARCH, 0.9),
    TriggerPattern("搜一下", ToolCategory.SEARCH, 0.95),
    TriggerPattern("查一下", ToolCategory.SEARCH, 0.9),
    TriggerPattern("查询", ToolCategory.SEARCH, 0.85),
    TriggerPattern("最新", ToolCategory.SEARCH, 0.8),
    TriggerPattern("新闻", ToolCategory.SEARCH, 0.85),
    TriggerPattern("今天", ToolCategory.SEARCH, 0.6),
    TriggerPattern("现在", ToolCategory.SEARCH, 0.5),
    TriggerPattern("目前", ToolCategory.SEARCH, 0.5),
]

# Negative patterns that reduce search confidence
SEARCH_NEGATIVE_PATTERNS = [
    # Code/programming contexts (user asking about search algorithms, not web search)
    TriggerPattern("binary search", ToolCategory.SEARCH, 0.5, is_negative=True),
    TriggerPattern("search algorithm", ToolCategory.SEARCH, 0.5, is_negative=True),
    TriggerPattern("search function", ToolCategory.SEARCH, 0.4, is_negative=True),
    TriggerPattern("search method", ToolCategory.SEARCH, 0.4, is_negative=True),
    TriggerPattern("linear search", ToolCategory.SEARCH, 0.5, is_negative=True),
    TriggerPattern("depth first search", ToolCategory.SEARCH, 0.5, is_negative=True),
    TriggerPattern("breadth first search", ToolCategory.SEARCH, 0.5, is_negative=True),

    # Hypothetical/general questions
    TriggerPattern("in general", ToolCategory.SEARCH, 0.2, is_negative=True),
    TriggerPattern("theoretically", ToolCategory.SEARCH, 0.2, is_negative=True),
    TriggerPattern("hypothetically", ToolCategory.SEARCH, 0.2, is_negative=True),
]

# Image generation trigger patterns
IMAGE_GENERATION_PATTERNS = [
    # Explicit generation requests (high confidence)
    TriggerPattern("generate image", ToolCategory.IMAGE_GENERATION, 1.0),
    TriggerPattern("generate an image", ToolCategory.IMAGE_GENERATION, 1.0),
    TriggerPattern("generate a image", ToolCategory.IMAGE_GENERATION, 1.0),
    TriggerPattern("create image", ToolCategory.IMAGE_GENERATION, 1.0),
    TriggerPattern("create an image", ToolCategory.IMAGE_GENERATION, 1.0),
    TriggerPattern("create a image", ToolCategory.IMAGE_GENERATION, 1.0),
    TriggerPattern("make image", ToolCategory.IMAGE_GENERATION, 1.0),
    TriggerPattern("make an image", ToolCategory.IMAGE_GENERATION, 1.0),
    TriggerPattern("make me an image", ToolCategory.IMAGE_GENERATION, 1.0),
    TriggerPattern("make a picture", ToolCategory.IMAGE_GENERATION, 1.0),
    TriggerPattern("create a picture", ToolCategory.IMAGE_GENERATION, 1.0),

    # Drawing requests (high confidence)
    TriggerPattern("draw a", ToolCategory.IMAGE_GENERATION, 0.95),
    TriggerPattern("draw an", ToolCategory.IMAGE_GENERATION, 0.95),
    TriggerPattern("draw me", ToolCategory.IMAGE_GENERATION, 0.95),
    TriggerPattern("sketch", ToolCategory.IMAGE_GENERATION, 0.8, requires_boundary=True),
    TriggerPattern("paint", ToolCategory.IMAGE_GENERATION, 0.7, requires_boundary=True),

    # Visual content requests (medium-high confidence)
    TriggerPattern("illustrate", ToolCategory.IMAGE_GENERATION, 0.85, requires_boundary=True),
    TriggerPattern("illustration", ToolCategory.IMAGE_GENERATION, 0.85, requires_boundary=True),
    TriggerPattern("visualize", ToolCategory.IMAGE_GENERATION, 0.8, requires_boundary=True),
    TriggerPattern("visualization", ToolCategory.IMAGE_GENERATION, 0.75, requires_boundary=True),
    TriggerPattern("infographic", ToolCategory.IMAGE_GENERATION, 0.9, requires_boundary=True),
    TriggerPattern("diagram", ToolCategory.IMAGE_GENERATION, 0.7, requires_boundary=True),
    TriggerPattern("artwork", ToolCategory.IMAGE_GENERATION, 0.85, requires_boundary=True),
    TriggerPattern("logo", ToolCategory.IMAGE_GENERATION, 0.8, requires_boundary=True),
    TriggerPattern("icon", ToolCategory.IMAGE_GENERATION, 0.6, requires_boundary=True),
    TriggerPattern("poster", ToolCategory.IMAGE_GENERATION, 0.75, requires_boundary=True),
    TriggerPattern("banner", ToolCategory.IMAGE_GENERATION, 0.7, requires_boundary=True),

    # Style-specific requests
    TriggerPattern("in the style of", ToolCategory.IMAGE_GENERATION, 0.7),
    TriggerPattern("photorealistic", ToolCategory.IMAGE_GENERATION, 0.85),
    TriggerPattern("cartoon", ToolCategory.IMAGE_GENERATION, 0.6, requires_boundary=True),
    TriggerPattern("anime", ToolCategory.IMAGE_GENERATION, 0.6, requires_boundary=True),
    TriggerPattern("pixel art", ToolCategory.IMAGE_GENERATION, 0.85),

    # Chinese triggers
    TriggerPattern("生成图片", ToolCategory.IMAGE_GENERATION, 1.0),
    TriggerPattern("生成图像", ToolCategory.IMAGE_GENERATION, 1.0),
    TriggerPattern("生成一张图", ToolCategory.IMAGE_GENERATION, 1.0),
    TriggerPattern("创建图片", ToolCategory.IMAGE_GENERATION, 1.0),
    TriggerPattern("画一张", ToolCategory.IMAGE_GENERATION, 0.95),
    TriggerPattern("画一个", ToolCategory.IMAGE_GENERATION, 0.95),
    TriggerPattern("画图", ToolCategory.IMAGE_GENERATION, 0.9),
    TriggerPattern("做图", ToolCategory.IMAGE_GENERATION, 0.9),
    TriggerPattern("出图", ToolCategory.IMAGE_GENERATION, 0.9),
    TriggerPattern("配图", ToolCategory.IMAGE_GENERATION, 0.85),
    TriggerPattern("插图", ToolCategory.IMAGE_GENERATION, 0.85),
    TriggerPattern("绘制", ToolCategory.IMAGE_GENERATION, 0.8),
]

# Image analysis trigger patterns
IMAGE_ANALYSIS_PATTERNS = [
    # Explicit analysis requests (high confidence)
    TriggerPattern("analyze image", ToolCategory.IMAGE_ANALYSIS, 1.0),
    TriggerPattern("analyze this image", ToolCategory.IMAGE_ANALYSIS, 1.0),
    TriggerPattern("analyze the image", ToolCategory.IMAGE_ANALYSIS, 1.0),
    TriggerPattern("analyze this picture", ToolCategory.IMAGE_ANALYSIS, 1.0),
    TriggerPattern("analyze the picture", ToolCategory.IMAGE_ANALYSIS, 1.0),

    # Description requests (high confidence)
    TriggerPattern("describe this image", ToolCategory.IMAGE_ANALYSIS, 1.0),
    TriggerPattern("describe the image", ToolCategory.IMAGE_ANALYSIS, 1.0),
    TriggerPattern("describe this picture", ToolCategory.IMAGE_ANALYSIS, 1.0),
    TriggerPattern("describe what you see", ToolCategory.IMAGE_ANALYSIS, 0.95),

    # Looking/seeing requests (high confidence)
    TriggerPattern("look at this image", ToolCategory.IMAGE_ANALYSIS, 1.0),
    TriggerPattern("look at the image", ToolCategory.IMAGE_ANALYSIS, 1.0),
    TriggerPattern("look at this picture", ToolCategory.IMAGE_ANALYSIS, 1.0),
    TriggerPattern("what's in this image", ToolCategory.IMAGE_ANALYSIS, 1.0),
    TriggerPattern("what is in this image", ToolCategory.IMAGE_ANALYSIS, 1.0),
    TriggerPattern("what do you see", ToolCategory.IMAGE_ANALYSIS, 0.9),
    TriggerPattern("can you see", ToolCategory.IMAGE_ANALYSIS, 0.8),

    # Context references (medium confidence)
    TriggerPattern("in the image", ToolCategory.IMAGE_ANALYSIS, 0.85),
    TriggerPattern("in this image", ToolCategory.IMAGE_ANALYSIS, 0.9),
    TriggerPattern("in the picture", ToolCategory.IMAGE_ANALYSIS, 0.85),
    TriggerPattern("in this picture", ToolCategory.IMAGE_ANALYSIS, 0.9),
    TriggerPattern("in the photo", ToolCategory.IMAGE_ANALYSIS, 0.85),
    TriggerPattern("in this photo", ToolCategory.IMAGE_ANALYSIS, 0.9),
    TriggerPattern("attached image", ToolCategory.IMAGE_ANALYSIS, 0.95),
    TriggerPattern("uploaded image", ToolCategory.IMAGE_ANALYSIS, 0.95),
    TriggerPattern("this screenshot", ToolCategory.IMAGE_ANALYSIS, 0.9),
    TriggerPattern("the screenshot", ToolCategory.IMAGE_ANALYSIS, 0.85),

    # OCR/text extraction
    TriggerPattern("read the text", ToolCategory.IMAGE_ANALYSIS, 0.85),
    TriggerPattern("extract text", ToolCategory.IMAGE_ANALYSIS, 0.9),
    TriggerPattern("ocr", ToolCategory.IMAGE_ANALYSIS, 0.95, requires_boundary=True),

    # Chinese triggers
    TriggerPattern("分析图片", ToolCategory.IMAGE_ANALYSIS, 1.0),
    TriggerPattern("分析图像", ToolCategory.IMAGE_ANALYSIS, 1.0),
    TriggerPattern("看看这张图", ToolCategory.IMAGE_ANALYSIS, 1.0),
    TriggerPattern("图片里", ToolCategory.IMAGE_ANALYSIS, 0.9),
    TriggerPattern("这张图", ToolCategory.IMAGE_ANALYSIS, 0.85),
    TriggerPattern("图中", ToolCategory.IMAGE_ANALYSIS, 0.8),
    TriggerPattern("照片中", ToolCategory.IMAGE_ANALYSIS, 0.85),
]


# =============================================================================
# Semantic Rules
# =============================================================================

def _check_question_intent(text: str) -> tuple[bool, float]:
    """Check if the query is a factual question that might need search."""
    question_starters = [
        (r'^what is\b', 0.5),
        (r'^what are\b', 0.5),
        (r'^who is\b', 0.7),
        (r'^who are\b', 0.7),
        (r'^when is\b', 0.6),
        (r'^when was\b', 0.6),
        (r'^when did\b', 0.6),
        (r'^where is\b', 0.6),
        (r'^where can\b', 0.7),
        (r'^how much\b', 0.6),
        (r'^how many\b', 0.5),
        (r'^how do i\b', 0.4),
        (r'^how to\b', 0.4),
        (r'^is there\b', 0.4),
        (r'^are there\b', 0.4),
        (r'^does .+ exist\b', 0.5),
        (r'^did .+ happen\b', 0.6),
    ]

    text_lower = text.lower().strip()
    for pattern, score in question_starters:
        if re.match(pattern, text_lower):
            return True, score

    # Check for question marks at end
    if text.strip().endswith('?'):
        return True, 0.3

    return False, 0.0


def _check_entity_query(text: str) -> tuple[bool, float]:
    """Check if the query asks about specific entities (likely needs search)."""
    entity_patterns = [
        (r'\b(company|corporation|inc|llc|ltd)\b', 0.6),
        (r'\b(ceo|founder|president|cto)\b', 0.7),
        (r'\b(product|service|app|software)\b', 0.4),
        (r'\b(country|city|state|region)\b', 0.4),
        (r'\b(university|college|school)\b', 0.5),
        (r'\b(movie|film|book|album|song)\b', 0.5),
        (r'\b(actor|actress|singer|author|artist)\b', 0.6),
    ]

    for pattern, score in entity_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True, score

    return False, 0.0


def _check_visual_description(text: str) -> tuple[bool, float]:
    """Check if the query describes a visual scene (image generation)."""
    visual_indicators = [
        (r'\bwith .+ background\b', 0.7),
        (r'\b(red|blue|green|yellow|purple|orange|pink|black|white) \w+\b', 0.4),
        (r'\b(standing|sitting|walking|running|flying)\b', 0.5),
        (r'\b(beautiful|stunning|majestic|epic|dramatic)\b', 0.5),
        (r'\b(landscape|portrait|scene|view)\b', 0.6),
        (r'\b(sunset|sunrise|night|day|morning|evening)\b', 0.5),
    ]

    for pattern, score in visual_indicators:
        if re.search(pattern, text, re.IGNORECASE):
            return True, score

    return False, 0.0


SEMANTIC_RULES = [
    SemanticRule(
        name="question_intent",
        categories=[ToolCategory.SEARCH],
        check=_check_question_intent,
    ),
    SemanticRule(
        name="entity_query",
        categories=[ToolCategory.SEARCH],
        check=_check_entity_query,
    ),
    SemanticRule(
        name="visual_description",
        categories=[ToolCategory.IMAGE_GENERATION],
        check=_check_visual_description,
    ),
]


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class ToolGateConfig:
    """Configuration for tool enablement decisions.

    Attributes:
        enable_threshold: Minimum confidence to enable tools (default 0.5)
        history_lookback: Number of history messages to check (default 4)
        history_weight: Weight multiplier for history matches (default 0.7)
        semantic_rules_enabled: Whether to use semantic rules (default True)
        log_decisions: Whether to log enablement decisions (default True)
    """

    enable_threshold: float = 0.5
    history_lookback: int = 4
    history_weight: float = 0.7
    semantic_rules_enabled: bool = True
    log_decisions: bool = True


# Default configuration
DEFAULT_CONFIG = ToolGateConfig()


# =============================================================================
# Core Functions
# =============================================================================

@lru_cache(maxsize=256)
def _get_all_patterns() -> tuple[TriggerPattern, ...]:
    """Get all trigger patterns (cached for performance)."""
    return tuple(
        SEARCH_PATTERNS +
        SEARCH_NEGATIVE_PATTERNS +
        IMAGE_GENERATION_PATTERNS +
        IMAGE_ANALYSIS_PATTERNS
    )


def _calculate_category_scores(
    text: str,
    config: ToolGateConfig,
) -> dict[ToolCategory, tuple[float, list[str]]]:
    """Calculate confidence scores for each tool category.

    Args:
        text: Text to analyze
        config: Configuration

    Returns:
        Dict mapping category to (score, matched_patterns)
    """
    scores: dict[ToolCategory, float] = {cat: 0.0 for cat in ToolCategory}
    matched: dict[ToolCategory, list[str]] = {cat: [] for cat in ToolCategory}

    # Check all patterns
    for pattern in _get_all_patterns():
        if pattern.matches(text):
            if pattern.is_negative:
                scores[pattern.category] -= pattern.score
            else:
                scores[pattern.category] = max(
                    scores[pattern.category],
                    pattern.score
                )
                matched[pattern.category].append(pattern.pattern)

    # Apply semantic rules
    if config.semantic_rules_enabled:
        for rule in SEMANTIC_RULES:
            matches, score = rule.check(text)
            if matches:
                for category in rule.categories:
                    # Semantic rules contribute additively but capped
                    scores[category] = min(
                        1.0,
                        scores[category] + score * 0.3
                    )
                    if score > 0:
                        matched[category].append(f"[rule:{rule.name}]")

    # Clamp scores to [0, 1]
    scores = {cat: max(0.0, min(1.0, score)) for cat, score in scores.items()}

    return {cat: (scores[cat], matched[cat]) for cat in ToolCategory}


def check_tool_enablement(
    query: str,
    history: list[dict] | None = None,
    has_image_attachments: bool = False,
    config: ToolGateConfig | None = None,
) -> ToolEnablementResult:
    """Check whether tools should be enabled for a query.

    This is the main entry point for tool enablement decisions.
    It analyzes the query and history to determine which tools
    should be enabled and with what confidence.

    Args:
        query: Current user query
        history: Conversation history as list of message dicts
        has_image_attachments: Whether the user has attached images
        config: Configuration (uses DEFAULT_CONFIG if not provided)

    Returns:
        ToolEnablementResult with decision and metadata
    """
    if config is None:
        config = DEFAULT_CONFIG

    history = history or []

    # Calculate scores for current query
    category_results = _calculate_category_scores(query, config)

    # Check history for additional context
    history_patterns: list[str] = []
    for msg in reversed(history[-config.history_lookback:]):
        if msg.get("role") != "user":
            continue
        content = msg.get("content") or ""
        if not content:
            continue

        hist_results = _calculate_category_scores(content, config)
        for cat, (score, patterns) in hist_results.items():
            if score > 0:
                # Apply history weight
                weighted_score = score * config.history_weight
                current_score, current_patterns = category_results[cat]
                if weighted_score > current_score:
                    category_results[cat] = (
                        weighted_score,
                        [f"[history]{p}" for p in patterns]
                    )
                    history_patterns.extend(patterns)

    # Handle image attachments
    if has_image_attachments:
        # Boost image analysis score significantly
        current_score, patterns = category_results[ToolCategory.IMAGE_ANALYSIS]
        category_results[ToolCategory.IMAGE_ANALYSIS] = (
            max(current_score, 0.9),
            patterns + ["[attachment:image]"]
        )

    # Extract final scores and patterns
    category_scores = {cat: score for cat, (score, _) in category_results.items()}
    all_matched_patterns = [
        pattern
        for _, patterns in category_results.values()
        for pattern in patterns
    ]

    # Determine if any category exceeds threshold
    max_score = max(category_scores.values())
    should_enable = max_score >= config.enable_threshold

    # Build result
    result = ToolEnablementResult(
        should_enable=should_enable,
        confidence=max_score,
        matched_patterns=list(set(all_matched_patterns)),
        matched_rules=[],
        category_scores=category_scores,
    )

    # Log decision if enabled
    if config.log_decisions:
        logger.debug(
            "tool_enablement_decision",
            should_enable=should_enable,
            confidence=round(max_score, 3),
            query_preview=query[:50],
            matched_patterns=result.matched_patterns[:5],
            category_scores={
                cat.value: round(score, 3)
                for cat, score in category_scores.items()
                if score > 0
            },
        )

    return result


def should_enable_tools(query: str, history: list[dict]) -> bool:
    """Decide whether to enable tools based on conversational context.

    This is the main API for tool gating. It returns a simple boolean
    for backward compatibility.

    Args:
        query: Current user query
        history: Conversation history as list of message dicts

    Returns:
        True if tools should be enabled, False otherwise
    """
    result = check_tool_enablement(query, history)
    return result.should_enable


def should_enable_image_tools(
    query: str,
    history: list[dict],
    has_image_attachments: bool = False,
) -> bool:
    """Decide whether to enable image-specific tools.

    Args:
        query: User query
        history: Conversation history
        has_image_attachments: Whether the user has attached images

    Returns:
        True if image tools should be enabled
    """
    result = check_tool_enablement(
        query,
        history,
        has_image_attachments=has_image_attachments,
    )

    # Check image-specific categories
    image_score = max(
        result.category_scores.get(ToolCategory.IMAGE_GENERATION, 0.0),
        result.category_scores.get(ToolCategory.IMAGE_ANALYSIS, 0.0),
    )

    return image_score >= DEFAULT_CONFIG.enable_threshold


def get_enabled_categories(
    query: str,
    history: list[dict] | None = None,
    has_image_attachments: bool = False,
    threshold: float | None = None,
) -> list[ToolCategory]:
    """Get list of tool categories that should be enabled.

    Args:
        query: User query
        history: Conversation history
        has_image_attachments: Whether images are attached
        threshold: Custom threshold (uses default if not provided)

    Returns:
        List of ToolCategory values that should be enabled
    """
    config = ToolGateConfig(
        enable_threshold=threshold or DEFAULT_CONFIG.enable_threshold
    )

    result = check_tool_enablement(
        query,
        history,
        has_image_attachments=has_image_attachments,
        config=config,
    )

    return [
        cat for cat, score in result.category_scores.items()
        if score >= config.enable_threshold
    ]


# Backward compatibility alias
should_enable_web_search = should_enable_tools
