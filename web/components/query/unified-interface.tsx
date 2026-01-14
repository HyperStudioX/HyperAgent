"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";
import { useSession } from "next-auth/react";
import { useTranslations } from "next-intl";
import {
  Send,
  Loader2,
  GraduationCap,
  TrendingUp,
  Code2,
  Newspaper,
  PenTool,
  BarChart3,
  Search,
  Check,
  Zap,
  Layers,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useChatStore } from "@/lib/stores/chat-store";
import { MessageBubble } from "@/components/chat/message-bubble";
import type { AgentType, ResearchScenario, ResearchDepth } from "@/lib/types";

// Larger icons for better visual presence
const AGENT_ICONS: Record<AgentType, React.ReactNode> = {
  chat: <Search className="w-5 h-5" />,
  research: <Search className="w-5 h-5" />,
  code: <Code2 className="w-5 h-5" />,
  writing: <PenTool className="w-5 h-5" />,
  data: <BarChart3 className="w-5 h-5" />,
};

const SCENARIO_ICONS: Record<ResearchScenario, React.ReactNode> = {
  academic: <GraduationCap className="w-5 h-5" />,
  market: <TrendingUp className="w-5 h-5" />,
  technical: <Code2 className="w-5 h-5" />,
  news: <Newspaper className="w-5 h-5" />,
};

const AGENT_KEYS: AgentType[] = ["research", "code", "writing", "data"];
const SCENARIO_KEYS: ResearchScenario[] = ["academic", "market", "technical", "news"];
const DEPTH_KEYS: ResearchDepth[] = ["fast", "deep"];

const DEPTH_ICONS: Record<ResearchDepth, React.ReactNode> = {
  fast: <Zap className="w-4 h-4" />,
  deep: <Layers className="w-4 h-4" />,
};

export function UnifiedInterface() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { status } = useSession();
  const t = useTranslations("home");
  const tAgents = useTranslations("agents");
  const tResearch = useTranslations("research");
  const tChat = useTranslations("chat");
  const [input, setInput] = useState("");
  const [selectedAgent, setSelectedAgent] = useState<AgentType | null>(null);
  const [selectedScenario, setSelectedScenario] = useState<ResearchScenario | null>(null);
  const [selectedDepth, setSelectedDepth] = useState<ResearchDepth>("fast");
  const [showResearchSubmenu, setShowResearchSubmenu] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const researchRef = useRef<HTMLDivElement>(null);
  const streamingContentRef = useRef("");
  const updateScheduledRef = useRef(false);

  // Throttled streaming content update using requestAnimationFrame
  const updateStreamingContent = useCallback((content: string) => {
    streamingContentRef.current = content;
    if (!updateScheduledRef.current) {
      updateScheduledRef.current = true;
      requestAnimationFrame(() => {
        setStreamingContent(streamingContentRef.current);
        updateScheduledRef.current = false;
      });
    }
  }, []);

  // Close research submenu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (researchRef.current && !researchRef.current.contains(event.target as Node)) {
        setShowResearchSubmenu(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Check for scenario from URL query parameter (from sidebar menu)
  useEffect(() => {
    const scenarioParam = searchParams.get("scenario");
    if (scenarioParam && SCENARIO_KEYS.includes(scenarioParam as ResearchScenario)) {
      setSelectedAgent("research");
      setSelectedScenario(scenarioParam as ResearchScenario);
      router.replace("/", { scroll: false });
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [searchParams, router]);

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
    loadConversation,
  } = useChatStore();

  const activeConversation = hasHydrated ? getActiveConversation() : undefined;
  const messages = activeConversation?.messages || [];

  // Load conversation messages when switching conversations
  useEffect(() => {
    // Don't load if session is still loading
    if (status === "loading") {
      return;
    }

    if (activeConversationId && hasHydrated) {
      const conversation = getActiveConversation();
      // Only load if messages haven't been loaded yet
      if (conversation && conversation.messages.length === 0) {
        // Only load from API if authenticated and not a local conversation
        const isLocal = activeConversationId.startsWith("local-");
        if (isLocal || status === "authenticated") {
          loadConversation(activeConversationId).catch(console.error);
        }
      }
    }
  }, [activeConversationId, hasHydrated, getActiveConversation, loadConversation, status]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingContent]);

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

    if (selectedAgent === "research" && selectedScenario) {
      handleResearch(userMessage);
    } else if (selectedAgent && selectedAgent !== "chat") {
      await handleAgentTask(userMessage, selectedAgent);
    } else {
      await handleChat(userMessage);
    }
  };

  const handleChat = async (userMessage: string, skipUserMessage = false) => {
    setStreamingContent("");

    let conversationId = activeConversationId;
    if (!conversationId || activeConversation?.type !== "chat") {
      conversationId = await createConversation("chat");
    }

    if (!skipUserMessage) {
      await addMessage(conversationId, { role: "user", content: userMessage });
    }

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
                updateStreamingContent(fullContent);
              } else if (event.type === "error") {
                fullContent = `Error: ${event.data}`;
                updateStreamingContent(fullContent);
              }
            } catch (e) {
              console.error("Parse error:", e);
            }
          }
        }
      }

      if (fullContent) {
        await addMessage(conversationId, { role: "assistant", content: fullContent });
      }
    } catch (error) {
      console.error("Chat error:", error);
      await addMessage(conversationId, { role: "assistant", content: tChat("connectionError") });
    } finally {
      setStreamingContent("");
      setLoading(false);
      setStreaming(false);
    }
  };

  const handleAgentTask = async (userMessage: string, agentType: AgentType) => {
    setStreamingContent("");

    // Determine the conversation type based on agent
    const conversationType = agentType === "research" ? "research" : agentType;

    // Always create a new conversation if:
    // 1. No active conversation exists
    // 2. Active conversation type doesn't match the selected agent type
    let conversationId = activeConversationId;
    const needsNewConversation = !conversationId ||
      !activeConversation ||
      activeConversation.type !== conversationType;

    if (needsNewConversation) {
      console.log(`[UnifiedInterface] Creating new ${conversationType} conversation`);
      conversationId = await createConversation(conversationType);
    } else {
      console.log(`[UnifiedInterface] Reusing existing ${conversationType} conversation`);
    }

    await addMessage(conversationId, { role: "user", content: userMessage });
    setLoading(true);
    setStreaming(true);

    let fullContent = "";

    try {
      const response = await fetch("/api/v1/query/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage, mode: agentType }),
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
                updateStreamingContent(fullContent);
              } else if (event.type === "error") {
                fullContent = `Error: ${event.data}`;
                updateStreamingContent(fullContent);
              }
            } catch (e) {
              console.error("Parse error:", e);
            }
          }
        }
      }

      if (fullContent) {
        await addMessage(conversationId, { role: "assistant", content: fullContent });
      }
    } catch (error) {
      console.error("Agent task error:", error);
      await addMessage(conversationId, { role: "assistant", content: tChat("connectionError") });
    } finally {
      setStreamingContent("");
      setLoading(false);
      setStreaming(false);
    }
  };

  const handleResearch = (query: string) => {
    if (!selectedScenario) return;
    const taskId = crypto.randomUUID();
    const taskInfo = { query, scenario: selectedScenario, depth: selectedDepth };
    localStorage.setItem(`task-${taskId}`, JSON.stringify(taskInfo));
    router.push(`/task/${taskId}`);
  };

  const handleRegenerate = async (messageId: string) => {
    if (!activeConversationId || isLoading) return;
    const messageIndex = messages.findIndex((m) => m.id === messageId);
    if (messageIndex === -1) return;

    let userMessage = "";
    for (let i = messageIndex - 1; i >= 0; i--) {
      if (messages[i].role === "user") {
        userMessage = messages[i].content;
        break;
      }
    }
    if (!userMessage) return;

    removeMessage(activeConversationId, messageId);
    await handleChat(userMessage, true);
  };

  const handleAgentSelect = (agent: AgentType) => {
    if (agent === "research") {
      // Toggle research submenu
      setShowResearchSubmenu(!showResearchSubmenu);
      return;
    }
    // For non-research agents, select directly
    if (selectedAgent === agent) {
      // Clicking same agent deselects it
      setSelectedAgent(null);
      setSelectedScenario(null);
    } else {
      setSelectedAgent(agent);
      setSelectedScenario(null);
    }
    setShowResearchSubmenu(false);
    inputRef.current?.focus();
  };

  const handleScenarioSelect = (scenario: ResearchScenario) => {
    if (selectedAgent === "research" && selectedScenario === scenario) {
      // Clicking same scenario deselects it
      setSelectedAgent(null);
      setSelectedScenario(null);
    } else {
      setSelectedAgent("research");
      setSelectedScenario(scenario);
    }
    setShowResearchSubmenu(false);
    inputRef.current?.focus();
  };

  const isProcessing = isLoading;
  const hasMessages = messages.length > 0 || streamingContent;

  const getPlaceholder = () => {
    if (selectedAgent === "research" && selectedScenario) {
      return t("researchPlaceholder", { scenario: tResearch(`${selectedScenario}.name`) });
    }
    if (selectedAgent === "code") return t("codePlaceholder");
    if (selectedAgent === "writing") return t("writingPlaceholder");
    if (selectedAgent === "data") return t("dataPlaceholder");
    return t("inputPlaceholder");
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Messages area */}
      {hasMessages && (
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-4xl mx-auto px-4 md:px-6 py-4 md:py-6">
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
                      message.role === "assistant" ? () => handleRegenerate(message.id) : undefined
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
                    isStreaming={true}
                  />
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>
        </div>
      )}

      {/* Input area */}
      <div
        className={cn(
          "flex flex-col",
          hasMessages ? "border-t border-border bg-background" : "flex-1 items-center justify-center"
        )}
      >
        <div
          className={cn(
            "w-full",
            hasMessages ? "max-w-4xl mx-auto px-4 md:px-6 py-4 md:py-6" : "max-w-3xl px-6 md:px-8"
          )}
        >
          {/* Welcome section - bigger and more impactful */}
          {!hasMessages && (
            <div className="text-center mb-12">
              {/* Logo + Product name */}
              <div
                className="flex items-center justify-center gap-3 mb-8 animate-slide-up"
                style={{ animationDelay: '0.1s', animationFillMode: 'backwards' }}
              >
                <div className="w-11 h-11 rounded-xl bg-foreground flex items-center justify-center text-background">
                  <Image
                    src="/images/logo.svg"
                    alt="HyperAgent"
                    width={26}
                    height={26}
                    priority
                    className="invert dark:invert-0"
                  />
                </div>
                <h1 className="text-3xl md:text-4xl font-bold text-foreground tracking-tight">
                  HyperAgent
                </h1>
              </div>

              {/* Subtitle - larger and more prominent */}
              <p
                className="text-muted-foreground text-lg md:text-xl leading-relaxed max-w-lg mx-auto animate-fade-in"
                style={{ animationDelay: '0.2s', animationFillMode: 'backwards' }}
              >
                {t("welcomeSubtitle")}
              </p>
            </div>
          )}

          {/* Input - large and prominent */}
          <div
            className={cn(
              "relative",
              !hasMessages && "animate-fade-in"
            )}
            style={!hasMessages ? { animationDelay: '0.3s', animationFillMode: 'backwards' } : undefined}
          >
            <div className={cn(
              "relative flex flex-col bg-card rounded-xl border border-border focus-within:border-foreground/30 transition-colors",
              !hasMessages && "shadow-sm"
            )}>
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={getPlaceholder()}
                className={cn(
                  "flex-1 w-full bg-transparent text-foreground placeholder:text-muted-foreground focus:outline-none resize-none leading-relaxed",
                  hasMessages
                    ? "min-h-[64px] max-h-[160px] px-4 py-3 text-base"
                    : "min-h-[100px] md:min-h-[110px] max-h-[200px] px-5 py-4 text-base"
                )}
                rows={hasMessages ? 2 : 3}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                    e.preventDefault();
                    handleSubmit();
                  }
                }}
              />
              {/* Bottom bar with hint and send button */}
              <div className="flex items-center justify-between px-4 md:px-6 py-3 border-t border-border/50">
                <p className="text-xs text-muted-foreground">
                  {tChat("pressEnterToSend")}
                </p>
                <button
                  onClick={handleSubmit}
                  disabled={!input.trim() || isProcessing}
                  className={cn(
                    "px-4 py-2 rounded-lg transition-colors min-h-[44px] flex items-center justify-center gap-2 font-medium text-sm",
                    input.trim() && !isProcessing
                      ? "bg-primary text-primary-foreground hover:bg-primary/90"
                      : "bg-secondary text-muted-foreground"
                  )}
                >
                  {isProcessing ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <>
                      <span>{tChat("send")}</span>
                      <Send className="w-4 h-4" />
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* Agent selection - compact pills with selection indicator (only on home view) */}
          {!hasMessages && (
            <div
              className="mt-6 animate-fade-in"
              style={{ animationDelay: '0.4s', animationFillMode: 'backwards' }}
            >
              <div className="flex items-center justify-center gap-2 flex-wrap">
                {AGENT_KEYS.map((agent) => {
                  const isSelected = selectedAgent === agent || (agent === "research" && selectedScenario);
                  return (
                    <div key={agent} className="relative" ref={agent === "research" ? researchRef : undefined}>
                      <button
                        onClick={() => handleAgentSelect(agent)}
                        onMouseEnter={() => agent === "research" && setShowResearchSubmenu(true)}
                        className={cn(
                          "relative flex items-center gap-2 px-3 py-2 rounded-lg transition-colors",
                          "text-sm font-medium",
                          isSelected
                            ? "bg-secondary text-foreground ring-1 ring-foreground/50"
                            : "bg-card text-muted-foreground border border-border hover:bg-secondary/50 hover:text-foreground"
                        )}
                      >
                        {/* Selection checkmark */}
                        {isSelected && (
                          <span className="flex items-center justify-center w-4 h-4 rounded-full bg-foreground text-background">
                            <Check className="w-3 h-3" strokeWidth={3} />
                          </span>
                        )}
                        {!isSelected && (
                          <span className="text-muted-foreground">
                            {AGENT_ICONS[agent]}
                          </span>
                        )}
                        <span>{tAgents(`${agent}.name`)}</span>
                        {agent === "research" && selectedScenario && (
                          <span className="text-xs text-muted-foreground">
                            · {tResearch(`${selectedScenario}.name`)} · {tResearch(`depth.${selectedDepth}.name`)}
                          </span>
                        )}
                      </button>

                      {/* Research scenarios submenu */}
                      {agent === "research" && showResearchSubmenu && (
                        <div
                          className="absolute left-0 top-full mt-2 z-50 animate-fade-in"
                          onMouseLeave={() => setShowResearchSubmenu(false)}
                        >
                          <div className="bg-card border border-border rounded-xl overflow-hidden min-w-[220px]">
                            {SCENARIO_KEYS.map((scenario) => (
                              <button
                                key={scenario}
                                onClick={() => handleScenarioSelect(scenario)}
                                className={cn(
                                  "w-full flex items-center gap-3 px-3 py-2.5 text-left transition-colors",
                                  "hover:bg-secondary/50",
                                  selectedScenario === scenario && "bg-secondary"
                                )}
                              >
                                {selectedScenario === scenario ? (
                                  <span className="flex items-center justify-center w-5 h-5 rounded-full bg-foreground text-background">
                                    <Check className="w-3 h-3" strokeWidth={3} />
                                  </span>
                                ) : (
                                  <span className="text-muted-foreground">
                                    {SCENARIO_ICONS[scenario]}
                                  </span>
                                )}
                                <div className="flex-1 min-w-0">
                                  <div className={cn(
                                    "text-sm font-medium",
                                    selectedScenario === scenario ? "text-foreground" : "text-foreground"
                                  )}>
                                    {tResearch(`${scenario}.name`)}
                                  </div>
                                  <div className="text-xs text-muted-foreground">
                                    {tResearch(`${scenario}.description`)}
                                  </div>
                                </div>
                              </button>
                            ))}
                            {/* Depth selector */}
                            <div className="border-t border-border px-3 py-2">
                              <div className="text-xs text-muted-foreground mb-2">
                                {tResearch("depth.label")}
                              </div>
                              <div className="flex gap-2">
                                {DEPTH_KEYS.map((depth) => (
                                  <button
                                    key={depth}
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setSelectedDepth(depth);
                                    }}
                                    className={cn(
                                      "flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-lg text-xs font-medium transition-colors",
                                      selectedDepth === depth
                                        ? "bg-foreground text-background"
                                        : "bg-secondary text-muted-foreground hover:text-foreground"
                                    )}
                                  >
                                    {DEPTH_ICONS[depth]}
                                    {tResearch(`depth.${depth}.name`)}
                                  </button>
                                ))}
                              </div>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
