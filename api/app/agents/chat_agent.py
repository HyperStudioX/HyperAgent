"""Chat agent using LangGraph for conversation management."""

from typing import Annotated, TypedDict

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from app.config import settings
from app.models.schemas import LLMProvider
from app.services.llm import llm_service


class ChatState(TypedDict):
    """State for the chat agent."""

    messages: Annotated[list[BaseMessage], add_messages]
    provider: LLMProvider
    model: str | None


SYSTEM_MESSAGE = SystemMessage(
    content="""You are HyperAgent, a helpful AI assistant. You are designed to help users with various tasks including coding, research, analysis, and general questions.

Be concise, accurate, and helpful. When providing code, use proper formatting with markdown code blocks and specify the language.

If you're unsure about something, say so rather than making things up."""
)


async def chat_node(state: ChatState) -> ChatState:
    """Process a chat message and generate a response."""
    llm = llm_service.get_llm(
        provider=state.get("provider", LLMProvider.ANTHROPIC),
        model=state.get("model"),
    )

    messages = [SYSTEM_MESSAGE] + state["messages"]
    response = await llm.ainvoke(messages)

    return {"messages": [response]}


def create_chat_graph():
    """Create the chat agent graph."""
    graph = StateGraph(ChatState)

    graph.add_node("chat", chat_node)
    graph.set_entry_point("chat")
    graph.add_edge("chat", END)

    return graph.compile()


# Compiled graph
chat_graph = create_chat_graph()


class ChatAgent:
    """Chat agent wrapper."""

    def __init__(self):
        self.graph = chat_graph

    async def chat(
        self,
        message: str,
        history: list[BaseMessage] | None = None,
        provider: LLMProvider = LLMProvider.ANTHROPIC,
        model: str | None = None,
    ) -> str:
        """Send a message and get a response."""
        messages = history or []
        messages.append(HumanMessage(content=message))

        result = await self.graph.ainvoke(
            {
                "messages": messages,
                "provider": provider,
                "model": model,
            }
        )

        return result["messages"][-1].content


chat_agent = ChatAgent()
