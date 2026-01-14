"use client";

import React, { useState, useRef, useEffect } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  Send,
  Loader2,
  GraduationCap,
  TrendingUp,
  Code2,
  Newspaper,
  ChevronDown,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useChatStore } from "@/lib/stores/chat-store";
import { MessageBubble } from "@/components/chat/message-bubble";
import type { ResearchScenario } from "@/lib/types";

const SCENARIO_ICONS: Record<ResearchScenario, React.ReactNode> = {
  academic: <GraduationCap className="w-4 h-4" />,
  market: <TrendingUp className="w-4 h-4" />,
  technical: <Code2 className="w-4 h-4" />,
  news: <Newspaper className="w-4 h-4" />,
};

const SCENARIO_KEYS: ResearchScenario[] = ["academic", "market", "technical", "news"];

export function UnifiedInterface() {
  const router = useRouter();
  const t = useTranslations("home");
  const tResearch = useTranslations("research");
  const tChat = useTranslations("chat");
  const [input, setInput] = useState("");
  const [selectedScenario, setSelectedScenario] = useState<ResearchScenario | null>(null);
  const [showScenarios, setShowScenarios] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const {
    activeConversationId,
    isLoading,
    hasHydrated,
    setLoading,
    setStreaming,
    addMessage,
    removeMessage,
    createConversation,
    getActiveConversation,
  } = useChatStore();

  const activeConversation = hasHydrated ? getActiveConversation() : undefined;
  const messages = activeConversation?.messages || [];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingContent]);

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 200) + "px";
    }
  }, [input]);

  const handleSubmit = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput("");

    if (selectedScenario) {
      handleResearch(userMessage);
    } else {
      await handleChat(userMessage);
    }
  };

  const handleChat = async (userMessage: string) => {
    setStreamingContent("");

    let conversationId = activeConversationId;
    if (!conversationId || activeConversation?.type !== "chat") {
      conversationId = createConversation("chat");
    }

    addMessage(conversationId, {
      role: "user",
      content: userMessage,
    });

    setLoading(true);
    setStreaming(true);

    let fullContent = "";

    try {
      const response = await fetch("/api/v1/query/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage, mode: "chat" }),
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const jsonStr = line.slice(6).trim();
            if (jsonStr === "[DONE]") continue;

            try {
              const event = JSON.parse(jsonStr);
              if (event.type === "token" && event.data) {
                fullContent += event.data;
                setStreamingContent(fullContent);
              } else if (event.type === "error") {
                fullContent = `Error: ${event.data}`;
                setStreamingContent(fullContent);
              }
            } catch (e) {
              console.error("Parse error:", e);
            }
          }
        }
      }

      if (fullContent) {
        addMessage(conversationId, {
          role: "assistant",
          content: fullContent,
        });
      }
    } catch (error) {
      console.error("Chat error:", error);
      addMessage(conversationId, {
        role: "assistant",
        content: tChat("connectionError"),
      });
    } finally {
      setStreamingContent("");
      setLoading(false);
      setStreaming(false);
    }
  };

  const handleResearch = (query: string) => {
    if (!selectedScenario) return;

    // Generate a unique task ID
    const taskId = crypto.randomUUID();

    // Store task info in localStorage for the task page to pick up
    const taskInfo = {
      query,
      scenario: selectedScenario,
      depth: "standard",
    };
    localStorage.setItem(`task-${taskId}`, JSON.stringify(taskInfo));

    // Navigate to the task progress page
    router.push(`/task/${taskId}`);
  };

  const handleRegenerate = async (messageId: string) => {
    if (!activeConversationId || isLoading) return;

    // Find the message index
    const messageIndex = messages.findIndex((m) => m.id === messageId);
    if (messageIndex === -1) return;

    // Find the preceding user message
    let userMessage = "";
    for (let i = messageIndex - 1; i >= 0; i--) {
      if (messages[i].role === "user") {
        userMessage = messages[i].content;
        break;
      }
    }

    if (!userMessage) return;

    // Remove the assistant message
    removeMessage(activeConversationId, messageId);

    // Regenerate the response
    await handleChat(userMessage);
  };

  const isProcessing = isLoading;
  const hasMessages = messages.length > 0 || streamingContent;

  // Get scenario name for placeholder
  const getScenarioName = (scenario: ResearchScenario) => tResearch(`${scenario}.name`);

  // Unified input view
  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Messages area (for chat mode) */}
      {hasMessages && (
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-2xl mx-auto px-4 py-6">
            <div className="space-y-1">
              {messages.map((message, index) => (
                <div
                  key={message.id}
                  className="animate-slide-up"
                  style={{ animationDelay: `${Math.min(index * 50, 200)}ms` }}
                >
                  <MessageBubble
                    message={message}
                    onRegenerate={
                      message.role === "assistant"
                        ? () => handleRegenerate(message.id)
                        : undefined
                    }
                  />
                </div>
              ))}
              {streamingContent && (
                <div className="animate-fade-in">
                  <MessageBubble
                    message={{
                      id: "streaming",
                      role: "assistant",
                      content: streamingContent,
                      createdAt: new Date(),
                    }}
                  />
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>
        </div>
      )}

      {/* Empty state / Input area */}
      <div className={cn(
        "flex flex-col",
        hasMessages
          ? "border-t border-border bg-background"
          : "flex-1 items-center justify-center"
      )}>
        <div className={cn(
          "w-full",
          hasMessages ? "max-w-2xl mx-auto px-4 py-4" : "max-w-xl px-4"
        )}>
          {/* Welcome message (only when no messages) */}
          {!hasMessages && (
            <div className="text-center mb-8 animate-fade-in">
              <div className="mx-auto mb-6">
                <Image
                  src="/images/logo-light.svg"
                  alt="HyperAgent"
                  width={48}
                  height={48}
                  className="dark:hidden mx-auto rounded-xl"
                />
                <Image
                  src="/images/logo-dark.svg"
                  alt="HyperAgent"
                  width={48}
                  height={48}
                  className="hidden dark:block mx-auto rounded-xl"
                />
              </div>
              <h1 className="text-2xl font-semibold text-foreground mb-2">
                {t("welcomeTitle")}
              </h1>
              <p className="text-muted-foreground leading-relaxed">
                {t("welcomeSubtitle")}
              </p>
            </div>
          )}

          {/* Input */}
          <div className="relative">
            <div className="relative flex items-end bg-card rounded-2xl border border-border focus-within:border-foreground/20 transition-colors shadow-sm">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={selectedScenario
                  ? t("researchPlaceholder", { scenario: getScenarioName(selectedScenario) })
                  : t("inputPlaceholder")
                }
                className="flex-1 min-h-[80px] max-h-[200px] px-5 py-4 bg-transparent text-base text-foreground placeholder:text-muted-foreground focus:outline-none resize-none leading-relaxed"
                rows={3}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit();
                  }
                }}
              />
              <div className="p-3">
                <button
                  onClick={handleSubmit}
                  disabled={!input.trim() || isProcessing}
                  className={cn(
                    "p-2.5 rounded-xl transition-colors",
                    input.trim() && !isProcessing
                      ? "bg-foreground text-background hover:bg-foreground/90"
                      : "bg-secondary text-muted-foreground"
                  )}
                >
                  {isProcessing ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <Send className="w-5 h-5" />
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* Deep Research selector */}
          <div className="mt-3">
            <button
              onClick={() => setShowScenarios(!showScenarios)}
              className={cn(
                "flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors",
                selectedScenario
                  ? "bg-foreground text-background"
                  : "text-muted-foreground hover:text-foreground hover:bg-secondary"
              )}
            >
              {selectedScenario ? (
                <>
                  {SCENARIO_ICONS[selectedScenario]}
                  <span>{getScenarioName(selectedScenario)}</span>
                  <span
                    role="button"
                    tabIndex={0}
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedScenario(null);
                      setShowScenarios(false);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.stopPropagation();
                        setSelectedScenario(null);
                        setShowScenarios(false);
                      }
                    }}
                    className="ml-1 hover:opacity-70 cursor-pointer"
                  >
                    ×
                  </span>
                </>
              ) : (
                <>
                  <span>{t("deepResearch")}</span>
                  <ChevronDown className={cn(
                    "w-3 h-3 transition-transform",
                    showScenarios && "rotate-180"
                  )} />
                </>
              )}
            </button>

            {/* Scenario options */}
            {showScenarios && !selectedScenario && (
              <div className="grid grid-cols-2 gap-2 mt-2 animate-fade-in">
                {SCENARIO_KEYS.map((scenario) => (
                  <button
                    key={scenario}
                    onClick={() => {
                      setSelectedScenario(scenario);
                      setShowScenarios(false);
                      inputRef.current?.focus();
                    }}
                    className="flex items-center gap-2 px-3 py-2.5 rounded-lg border border-border bg-card text-left text-muted-foreground hover:bg-secondary/50 hover:text-foreground transition-colors"
                  >
                    {SCENARIO_ICONS[scenario]}
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium truncate">
                        {tResearch(`${scenario}.name`)}
                      </div>
                      <div className="text-xs opacity-60 truncate">
                        {tResearch(`${scenario}.description`)}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
