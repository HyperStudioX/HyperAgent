from typing import AsyncGenerator, Any

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.language_models import BaseChatModel

from app.config import settings
from app.models.schemas import LLMProvider, ChatMessage, MessageRole
from app.ai.model_tiers import ModelTier, get_model_for_tier, get_tier_for_task, get_provider_for_tier


def extract_text_from_content(content: Any) -> str:
    """Extract text content from structured LLM chunk content.
    
    Handles various content formats:
    - String: returns as-is
    - List of content blocks: extracts text from text blocks, skips tool_use blocks
    - Dict: extracts text field if present
    - Other: converts to string
    
    Args:
        content: Content from LLM chunk (can be str, list, dict, etc.)
        
    Returns:
        Extracted text as string
    """
    if isinstance(content, str):
        return content
    
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict):
                # Extract text from text blocks
                if item.get("type") == "text" and "text" in item:
                    text_parts.append(str(item["text"]))
                # Skip tool_use blocks (not meant for display)
                elif item.get("type") == "tool_use":
                    continue
                # Skip input_json_delta (intermediate states)
                elif item.get("type") == "input_json_delta":
                    continue
                # Try to extract text field if present
                elif "text" in item:
                    text_parts.append(str(item["text"]))
            elif isinstance(item, str):
                text_parts.append(item)
            else:
                # Fallback: convert to string
                text_parts.append(str(item))
        return "".join(text_parts)
    
    if isinstance(content, dict):
        # Try to extract text field
        if "text" in content:
            return str(content["text"])
        # Skip tool_use blocks
        if content.get("type") == "tool_use":
            return ""
        # Skip input_json_delta
        if content.get("type") == "input_json_delta":
            return ""
    
    # Fallback: convert to string
    return str(content)


class LLMService:
    """Unified LLM service supporting multiple providers."""

    def __init__(self):
        self._anthropic: ChatAnthropic | None = None
        self._openai: ChatOpenAI | None = None
        self._gemini: ChatGoogleGenerativeAI | None = None

    def _get_anthropic(self, model: str | None = None) -> ChatAnthropic:
        """Get Anthropic client."""
        if not settings.anthropic_api_key:
            raise ValueError("Anthropic API key not configured")
        return ChatAnthropic(
            api_key=settings.anthropic_api_key,
            model=model or settings.default_model_anthropic,
            streaming=True,
        )

    def _get_openai(self, model: str | None = None) -> ChatOpenAI:
        """Get OpenAI client."""
        if not settings.openai_api_key:
            raise ValueError("OpenAI API key not configured")
        return ChatOpenAI(
            api_key=settings.openai_api_key,
            model=model or settings.default_model_openai,
            streaming=True,
        )

    def _get_gemini(self, model: str | None = None) -> ChatGoogleGenerativeAI:
        """Get Google Gemini client."""
        if not settings.gemini_api_key:
            raise ValueError("Gemini API key not configured")
        return ChatGoogleGenerativeAI(
            google_api_key=settings.gemini_api_key,
            model=model or settings.default_model_gemini,
            streaming=True,
        )

    def get_llm(
        self, provider: LLMProvider = LLMProvider.ANTHROPIC, model: str | None = None
    ) -> BaseChatModel:
        """Get LLM instance for the specified provider."""
        if provider == LLMProvider.ANTHROPIC:
            return self._get_anthropic(model)
        elif provider == LLMProvider.OPENAI:
            return self._get_openai(model)
        elif provider == LLMProvider.GEMINI:
            return self._get_gemini(model)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def get_llm_for_tier(
        self,
        tier: ModelTier,
        provider: LLMProvider | None = None,
        model_override: str | None = None,
    ) -> BaseChatModel:
        """Get LLM for a specific tier, with optional model override.

        Args:
            tier: The model tier to use
            provider: The LLM provider (if None, auto-selects based on tier configuration)
            model_override: Optional model override (bypasses tier selection)

        Returns:
            LLM instance configured for the specified tier
        """
        # Auto-select provider based on tier if not explicitly provided
        if provider is None:
            provider = get_provider_for_tier(tier, settings.tier_providers)

        if model_override:
            return self.get_llm(provider, model_override)

        model = get_model_for_tier(tier, provider, settings.tier_mappings)
        return self.get_llm(provider, model)

    def choose_llm_for_task(
        self,
        task_type: str,
        provider: LLMProvider | None = None,
        tier_override: ModelTier | None = None,
        model_override: str | None = None,
    ) -> BaseChatModel:
        """Choose LLM based on task type with auto-routing.

        Priority: model_override > tier_override > auto-routing

        Args:
            task_type: Type of task (e.g., "research", "chat", "code")
            provider: The LLM provider (if None, auto-selects based on tier configuration)
            tier_override: Optional tier override (bypasses auto-routing)
            model_override: Optional model override (bypasses tier and auto-routing)

        Returns:
            LLM instance configured for the task
        """
        tier = tier_override or get_tier_for_task(task_type)

        # Auto-select provider based on tier if not explicitly provided
        if provider is None:
            provider = get_provider_for_tier(tier, settings.tier_providers)

        if model_override:
            return self.get_llm(provider, model_override)

        return self.get_llm_for_tier(tier, provider)

    def convert_messages(self, messages: list[ChatMessage]) -> list:
        """Convert chat messages to LangChain format."""
        converted = []
        for msg in messages:
            if msg.role == MessageRole.USER:
                converted.append(HumanMessage(content=msg.content))
            elif msg.role == MessageRole.ASSISTANT:
                converted.append(AIMessage(content=msg.content))
            elif msg.role == MessageRole.SYSTEM:
                converted.append(SystemMessage(content=msg.content))
        return converted

    async def chat(
        self,
        message: str,
        history: list[ChatMessage] | None = None,
        provider: LLMProvider = LLMProvider.ANTHROPIC,
        model: str | None = None,
        system_prompt: str | None = None,
    ) -> str:
        """Send a chat message and get a response."""
        llm = self.get_llm(provider, model)

        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        if history:
            messages.extend(self.convert_messages(history))
        messages.append(HumanMessage(content=message))

        response = await llm.ainvoke(messages)
        return response.content

    async def stream_chat(
        self,
        message: str,
        history: list[ChatMessage] | None = None,
        provider: LLMProvider = LLMProvider.ANTHROPIC,
        model: str | None = None,
        system_prompt: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream a chat response token by token."""
        llm = self.get_llm(provider, model)

        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        if history:
            messages.extend(self.convert_messages(history))
        messages.append(HumanMessage(content=message))

        async for chunk in llm.astream(messages):
            if chunk.content:
                yield extract_text_from_content(chunk.content)

    async def generate_title(
        self,
        message: str,
        provider: LLMProvider = LLMProvider.ANTHROPIC,
        model: str | None = None,
    ) -> str:
        """Generate a concise title for a conversation based on the user's message.
        
        Args:
            message: The user's input message
            provider: LLM provider to use
            model: Optional model override
            
        Returns:
            A concise title (max 5-6 words)
        """
        llm = self.get_llm(provider, model)
        
        prompt = (
            "Generate a very concise, meaningful title for an AI conversation "
            "that starts with the following user message. "
            "Respond ONLY with the title text (no quotes, no period, max 6 words):\n\n"
            f"'{message}'"
        )
        
        messages = [HumanMessage(content=prompt)]
        response = await llm.ainvoke(messages)
        title = extract_text_from_content(response.content).strip()
        
        # Clean up the title
        if title.startswith('"') and title.endswith('"'):
            title = title[1:-1]
        elif title.startswith("'") and title.endswith("'"):
            title = title[1:-1]
            
        return title


# Global instance
llm_service = LLMService()
