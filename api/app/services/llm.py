from typing import AsyncGenerator

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.language_models import BaseChatModel

from app.config import settings
from app.models.schemas import LLMProvider, ChatMessage, MessageRole


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
                yield chunk.content


# Global instance
llm_service = LLMService()
