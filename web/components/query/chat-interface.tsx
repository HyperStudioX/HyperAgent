"use client";

import React, { useState, useRef, useEffect, useCallback, useMemo, memo } from "react";
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
import { useShallow } from "zustand/shallow";
import { MessageBubble } from "@/components/chat/message-bubble";
import { FileUploadButton } from "@/components/chat/file-upload-button";
import { VoiceInputButton } from "@/components/chat/voice-input-button";
import { AttachmentPreview } from "@/components/chat/attachment-preview";
import { useFileUpload } from "@/lib/hooks/use-file-upload";
import { useGoogleDrivePicker } from "@/lib/hooks/use-google-drive-picker";
import type { AgentType, ResearchScenario, ResearchDepth, FileAttachment } from "@/lib/types";

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

// Memoized message list to prevent re-renders on input changes
interface MessageListProps {
    messages: any[];
    streamingContent: string;
    isLoading: boolean;
    agentStatus: string | null;
    streamingEvents: any[];
    streamingVisualizations: any[];
    streamingStartTime: Date;
    onRegenerate: (messageId: string) => void;
    messagesEndRef: React.RefObject<HTMLDivElement>;
}

const MessageList = memo(function MessageList({
    messages,
    streamingContent,
    isLoading,
    agentStatus,
    streamingEvents,
    streamingVisualizations,
    streamingStartTime,
    onRegenerate,
    messagesEndRef,
}: MessageListProps) {
    return (
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
                            message.role === "assistant" ? () => onRegenerate(message.id) : undefined
                        }
                    />
                </div>
            ))}
            {(streamingContent || isLoading) && (
                <div className="animate-fade-in">
                    <MessageBubble
                        message={{
                            id: "streaming",
                            role: "assistant",
                            content: streamingContent || "",
                            createdAt: streamingStartTime,
                        }}
                        isStreaming={true}
                        status={agentStatus}
                        agentEvents={streamingEvents}
                        visualizations={streamingVisualizations}
                    />
                </div>
            )}
            <div ref={messagesEndRef} />
        </div>
    );
});

export function ChatInterface() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const { status: sessionStatus } = useSession();
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
    const [agentStatus, setAgentStatus] = useState<string | null>(null);
    const [streamingEvents, setStreamingEvents] = useState<any[]>([]);
    const [streamingVisualizations, setStreamingVisualizations] = useState<{ data: string; mimeType: "image/png" | "text/html" }[]>([]);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);
    const researchRef = useRef<HTMLDivElement>(null);
    const streamingContentRef = useRef("");
    const updateScheduledRef = useRef(false);
    const streamingStartTimeRef = useRef<Date>(new Date());

    // File upload hook
    const {
        attachments,
        isUploading,
        addFiles,
        removeAttachment,
        clearAttachments,
        getUploadedFileIds,
    } = useFileUpload({ maxFiles: 10 });

    // Google Drive picker hook
    const { openPicker: openGoogleDrivePicker, error: googleDriveError } = useGoogleDrivePicker({
        onFilesSelected: (driveFiles) => {
            // TODO: Download Google Drive files and convert to local files
            // For now, just show a placeholder
            alert(tChat("googleDriveSoon", { count: driveFiles.length }));
        },
        multiSelect: true,
    });

    // Handle attachment source selection
    const handleSourceSelect = (sourceId: string) => {
        if (sourceId === "google-drive") {
            openGoogleDrivePicker();
        }
    };

    // Token batching for smoother rendering
    const tokenBatchRef = useRef<string[]>([]);
    const batchTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const BATCH_INTERVAL_MS = 50; // Batch tokens every 50ms for smooth rendering

    // Event batching for smoother AgentProgress updates
    const eventBatchRef = useRef<any[]>([]);
    const eventUpdateScheduledRef = useRef(false);

    // Throttled streaming content update using requestAnimationFrame with batching
    const updateStreamingContent = useCallback((content: string) => {
        // Only update if content actually changed
        if (streamingContentRef.current === content) return;
        streamingContentRef.current = content;
        if (!updateScheduledRef.current) {
            updateScheduledRef.current = true;
            // Use requestAnimationFrame for smooth updates
            requestAnimationFrame(() => {
                updateScheduledRef.current = false;
                // Only set state if we're still streaming (component not unmounted)
                setStreamingContent(prev => {
                    // Prevent unnecessary updates
                    if (prev === streamingContentRef.current) return prev;
                    return streamingContentRef.current;
                });
            });
        }
    }, []);

    // Batch tokens and flush periodically for smoother rendering
    const appendTokenBatch = useCallback((token: string) => {
        tokenBatchRef.current.push(token);

        // If no flush scheduled, schedule one
        if (!batchTimeoutRef.current) {
            batchTimeoutRef.current = setTimeout(() => {
                // Flush all batched tokens at once
                const batchedContent = tokenBatchRef.current.join("");
                tokenBatchRef.current = [];
                batchTimeoutRef.current = null;

                if (batchedContent) {
                    streamingContentRef.current += batchedContent;
                    updateStreamingContent(streamingContentRef.current);
                }
            }, BATCH_INTERVAL_MS);
        }
    }, [updateStreamingContent]);

    // Flush any remaining tokens immediately
    const flushTokenBatch = useCallback(() => {
        if (batchTimeoutRef.current) {
            clearTimeout(batchTimeoutRef.current);
            batchTimeoutRef.current = null;
        }
        if (tokenBatchRef.current.length > 0) {
            const batchedContent = tokenBatchRef.current.join("");
            tokenBatchRef.current = [];
            streamingContentRef.current += batchedContent;
            updateStreamingContent(streamingContentRef.current);
        }
    }, [updateStreamingContent]);

    // Batched event update to reduce AgentProgress re-renders
    const batchEventUpdate = useCallback((event: any) => {
        eventBatchRef.current.push(event);
        if (!eventUpdateScheduledRef.current) {
            eventUpdateScheduledRef.current = true;
            requestAnimationFrame(() => {
                const batch = eventBatchRef.current;
                eventBatchRef.current = [];
                eventUpdateScheduledRef.current = false;
                if (batch.length > 0) {
                    setStreamingEvents(prev => [...prev, ...batch]);
                }
            });
        }
    }, []);

    // Reset streaming events (for starting a new stream)
    const resetStreamingEvents = useCallback((initialEvents: any[] = []) => {
        eventBatchRef.current = [];
        eventUpdateScheduledRef.current = false;
        setStreamingEvents(initialEvents);
    }, []);

    // Throttled agent status update
    const agentStatusRef = useRef<string | null>(null);
    const statusUpdateScheduledRef = useRef(false);
    const throttledSetAgentStatus = useCallback((status: string | null) => {
        agentStatusRef.current = status;
        if (!statusUpdateScheduledRef.current) {
            statusUpdateScheduledRef.current = true;
            requestAnimationFrame(() => {
                setAgentStatus(agentStatusRef.current);
                statusUpdateScheduledRef.current = false;
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

    // Consolidate store selectors into a single subscription for better performance
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
        conversations,
    } = useChatStore(
        useShallow((state) => ({
            activeConversationId: state.activeConversationId,
            isLoading: state.isLoading,
            hasHydrated: state.hasHydrated,
            setLoading: state.setLoading,
            setStreaming: state.setStreaming,
            addMessage: state.addMessage,
            removeMessage: state.removeMessage,
            createConversation: state.createConversation,
            getActiveConversation: state.getActiveConversation,
            loadConversation: state.loadConversation,
            conversations: state.conversations,
        }))
    );

    const activeConversation = hasHydrated ? getActiveConversation() : undefined;
    const messages = activeConversation?.messages || [];

    // Track which conversations have been loaded to prevent infinite loops when messages.length === 0
    const loadedConversationsRef = useRef<Set<string>>(new Set());

    // Load conversation messages when switching conversations
    useEffect(() => {
        // Don't load if session is still loading
        if (sessionStatus === "loading") {
            return;
        }

        if (activeConversationId && hasHydrated && !loadedConversationsRef.current.has(activeConversationId)) {
            const conversation = getActiveConversation();
            const isLocal = activeConversationId.startsWith("local-");

            if (isLocal) {
                loadedConversationsRef.current.add(activeConversationId);
                return;
            }

            // Only load if messages haven't been loaded yet and it's not a local conversation
            if (conversation && conversation.messages.length === 0) {
                if (sessionStatus === "authenticated") {
                    loadedConversationsRef.current.add(activeConversationId);
                    loadConversation(activeConversationId).catch((error) => {
                        console.error("[UnifiedInterface] Failed to load conversation:", error);
                        // Remove from set on error to allow retry
                        loadedConversationsRef.current.delete(activeConversationId);
                    });
                }
            } else if (conversation) {
                // If it already has messages, consider it loaded
                loadedConversationsRef.current.add(activeConversationId);
            }
        }
    }, [activeConversationId, hasHydrated, getActiveConversation, loadConversation, sessionStatus]);

    const scrollToBottomRef = useRef<number | null>(null);
    const scrollToBottom = useCallback(() => {
        // Throttle scroll updates to avoid performance issues during streaming
        if (scrollToBottomRef.current) return;
        scrollToBottomRef.current = requestAnimationFrame(() => {
            scrollToBottomRef.current = null;
            messagesEndRef.current?.scrollIntoView({ behavior: "auto" });
        });
    }, []);

    // Separate effect for messages to avoid re-running on every streamingContent change
    useEffect(() => {
        scrollToBottom();
    }, [messages, scrollToBottom]);

    // Throttled scroll for streaming - only scroll occasionally during streaming
    const lastScrollTimeRef = useRef<number>(0);
    useEffect(() => {
        if (!streamingContent) return;
        const now = Date.now();
        // Only scroll every 100ms during streaming to avoid performance issues
        if (now - lastScrollTimeRef.current > 100) {
            lastScrollTimeRef.current = now;
            scrollToBottom();
        }
    }, [streamingContent, scrollToBottom]);


    const getConversationAttachmentIds = useCallback((conversationMessages: typeof messages) => {
        const ids = conversationMessages.flatMap((message) =>
            message.attachments?.map((attachment) => attachment.id) || []
        );
        return Array.from(new Set(ids));
    }, []);

    const handleSubmit = async () => {
        if (!input.trim() || isLoading || isUploading) return;

        const userMessage = input.trim();
        const attachmentIds = getUploadedFileIds();
        const messageAttachments = attachments.filter(a => a.status === 'uploaded');
        setInput("");
        clearAttachments();

        if (selectedAgent === "research" && selectedScenario) {
            handleResearch(userMessage);
        } else if (selectedAgent && selectedAgent !== "chat") {
            await handleAgentTask(userMessage, selectedAgent, attachmentIds, messageAttachments);
        } else if (!selectedAgent && activeConversation?.type && activeConversation.type !== "chat") {
            await handleAgentTask(
                userMessage,
                activeConversation.type as AgentType,
                attachmentIds,
                messageAttachments
            );
        } else {
            await handleChat(userMessage, false, attachmentIds, messageAttachments);
        }
    };

    const handleChat = async (
        userMessage: string,
        skipUserMessage = false,
        attachmentIds: string[] = [],
        messageAttachments: FileAttachment[] = []
    ) => {
        setStreamingContent("");
        streamingContentRef.current = "";
        tokenBatchRef.current = [];
        setAgentStatus(null);
        resetStreamingEvents();
        setStreamingVisualizations([]);

        let conversationId = activeConversationId;
        if (!conversationId || activeConversation?.type !== "chat") {
            conversationId = await createConversation("chat");
        }

        // Get conversation messages for context BEFORE adding the new message
        // The backend will add the current message separately
        const conversationForHistory =
            conversations.find((conversation) => conversation.id === conversationId) || activeConversation;
        const conversationMessages = conversationForHistory?.messages || [];
        const history = conversationMessages
            .filter(msg => msg.role === "user" || msg.role === "assistant")
            .map(msg => ({
                role: msg.role,
                content: msg.content,
                metadata: msg.metadata || null,
            }));
        const historyAttachmentIds = getConversationAttachmentIds(conversationMessages);
        const combinedAttachmentIds = Array.from(new Set([...historyAttachmentIds, ...attachmentIds]));

        if (!skipUserMessage) {
            await addMessage(conversationId, {
                role: "user",
                content: userMessage,
                attachments: messageAttachments
            });
        }

        setLoading(true);
        setStreaming(true);
        streamingStartTimeRef.current = new Date();

        // Add initial thinking event immediately for instant feedback
        const thinkingEvent = {
            type: "stage",
            name: "thinking",
            description: tChat("agent.thinking"),
            status: "running",
        };
        resetStreamingEvents([thinkingEvent]);

        let fullContent = "";
        const collectedEvents: any[] = [thinkingEvent];
        const collectedVisualizations: { data: string; mimeType: "image/png" | "text/html" }[] = [];

        try {

            const response = await fetch("/api/v1/query/stream", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: userMessage,
                    mode: "chat",
                    attachment_ids: combinedAttachmentIds,
                    conversation_id: conversationId?.startsWith("local-") ? null : conversationId,
                    history: history,
                }),
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
                    // Skip empty lines
                    if (!line.trim()) continue;

                    // Handle SSE format: "data: {...}" or "event: message\ndata: {...}"
                    if (line.startsWith("data: ")) {
                        const jsonStr = line.slice(6).trim();
                        if (jsonStr === "[DONE]" || !jsonStr) continue;

                        try {
                            const event = JSON.parse(jsonStr);

                            if (event.type === "token" && event.data) {
                                fullContent += event.data;
                                // Simply update streaming content - search queries come via tool_call events
                                updateStreamingContent(fullContent);
                                throttledSetAgentStatus(null);
                            } else if (event.type === "stage") {
                                // Flush tokens before stage change for immediate visual feedback
                                flushTokenBatch();
                                const stageDescription = event.description || event.data?.description;
                                throttledSetAgentStatus(stageDescription);
                                collectedEvents.push(event);
                                setStreamingEvents(prev => [...prev.filter(e => e.type !== 'stage' || (e.status || e.data?.status) !== 'pending'), event]);
                            } else if (event.type === "tool_call") {
                                // Handle both flat structure and legacy data wrapper
                                const toolName = event.tool || event.data?.tool || "web";
                                const args = event.args || event.data?.args || {};
                                if (toolName === "web_search" || toolName === "google_search" || toolName === "web") {
                                    throttledSetAgentStatus(tChat("agent.searching", { query: args.query || "web" }));
                                } else {
                                    throttledSetAgentStatus(tChat("agent.executing", { tool: toolName }));
                                }
                                collectedEvents.push(event);
                                batchEventUpdate(event);
                            } else if (event.type === "tool_result") {
                                collectedEvents.push(event);
                                batchEventUpdate(event);
                            } else if (event.type === "routing") {
                                // Handle routing decision events
                                collectedEvents.push(event);
                                batchEventUpdate(event);
                            } else if (event.type === "handoff") {
                                // Handle agent handoff events
                                const target = event.target || "";
                                throttledSetAgentStatus(tChat("agent.handoffTo", { target }));
                                collectedEvents.push(event);
                                batchEventUpdate(event);
                            } else if (event.type === "source") {
                                // Handle source events from search
                                collectedEvents.push(event);
                                batchEventUpdate(event);
                            } else if (event.type === "code_result") {
                                // Handle code execution results
                                collectedEvents.push(event);
                                batchEventUpdate(event);
                            } else if (event.type === "visualization" && event.data && event.mime_type) {
                                // Handle visualization event from data analytics agent
                                const visualization = {
                                    data: event.data as string,
                                    mimeType: event.mime_type as "image/png" | "text/html",
                                };
                                collectedVisualizations.push(visualization);
                                setStreamingVisualizations(prev => [...prev, visualization]);
                                collectedEvents.push(event);
                            } else if (event.type === "error") {
                                fullContent = tChat("agent.error", { error: event.data });
                                updateStreamingContent(fullContent);
                            } else if (event.type === "complete") {
                                // Stream complete, break out of loop
                                break;
                            }
                        } catch (e) {
                            console.error("[SSE Parse Error]", e, "Line:", line);
                        }
                    } else if (line.startsWith("event: ")) {
                        // SSE event type line, can be ignored as we parse data lines
                        continue;
                    }
                }
            }

            if (fullContent) {
                const sanitizedContent = fullContent;
                await addMessage(conversationId, {
                    role: "assistant",
                    content: sanitizedContent,
                    metadata: (collectedEvents.length || collectedVisualizations.length) ? {
                        agentEvents: collectedEvents.length ? collectedEvents : undefined,
                        visualizations: collectedVisualizations.length ? collectedVisualizations : undefined,
                    } : undefined,
                });
            }
        } catch (error) {
            console.error("Chat error:", error);
            await addMessage(conversationId, { role: "assistant", content: tChat("connectionError") });
        } finally {
            flushTokenBatch();
            setStreamingContent("");
            streamingContentRef.current = "";
            setAgentStatus(null);
            resetStreamingEvents();
            setStreamingVisualizations([]);
            setLoading(false);
            setStreaming(false);
        }
    };

    const handleAgentTask = async (
        userMessage: string,
        agentType: AgentType,
        attachmentIds: string[] = [],
        messageAttachments: FileAttachment[] = []
    ) => {
        setStreamingContent("");
        streamingContentRef.current = "";
        tokenBatchRef.current = [];
        setAgentStatus(null);
        resetStreamingEvents();
        setStreamingVisualizations([]);

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
            conversationId = await createConversation(conversationType);
        }

        if (!conversationId) {
            throw new Error("Failed to get conversation ID");
        }

        // Get conversation messages for context BEFORE adding the new message
        // The backend will add the current message separately
        const conversationForHistory =
            conversations.find((conversation) => conversation.id === conversationId) || activeConversation;
        const conversationMessages = conversationForHistory?.messages || [];
        const history = conversationMessages
            .filter(msg => msg.role === "user" || msg.role === "assistant")
            .map(msg => ({
                role: msg.role,
                content: msg.content,
                metadata: msg.metadata || null,
            }));
        const historyAttachmentIds = getConversationAttachmentIds(conversationMessages);
        const combinedAttachmentIds = agentType === "research"
            ? attachmentIds
            : Array.from(new Set([...historyAttachmentIds, ...attachmentIds]));

        await addMessage(conversationId, {
            role: "user",
            content: userMessage,
            attachments: messageAttachments
        });
        setLoading(true);
        setStreaming(true);
        streamingStartTimeRef.current = new Date();

        // Add initial thinking event immediately for instant feedback
        const thinkingEvent = {
            type: "stage",
            name: "thinking",
            description: tChat("agent.thinking"),
            status: "running",
        };
        resetStreamingEvents([thinkingEvent]);

        let fullContent = "";
        const collectedEvents: any[] = [thinkingEvent];
        const collectedVisualizations: { data: string; mimeType: "image/png" | "text/html" }[] = [];

        try {

            const response = await fetch("/api/v1/query/stream", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: userMessage,
                    mode: agentType,
                    attachment_ids: combinedAttachmentIds,
                    conversation_id: conversationId?.startsWith("local-") ? null : conversationId,
                    history: history,
                }),
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
                    // Skip empty lines
                    if (!line.trim()) continue;

                    // Handle SSE format: "data: {...}" or "event: message\ndata: {...}"
                    if (line.startsWith("data: ")) {
                        const jsonStr = line.slice(6).trim();
                        if (jsonStr === "[DONE]" || !jsonStr) continue;

                        try {
                            const event = JSON.parse(jsonStr);

                            if (event.type === "token" && event.data) {
                                fullContent += event.data;
                                // Simply update streaming content - search queries come via tool_call events
                                updateStreamingContent(fullContent);
                                throttledSetAgentStatus(null);
                            } else if (event.type === "stage") {
                                // Flush tokens before stage change for immediate visual feedback
                                flushTokenBatch();
                                const stageDescription = event.description || event.data?.description;
                                throttledSetAgentStatus(stageDescription);
                                collectedEvents.push(event);
                                setStreamingEvents(prev => [...prev.filter(e => e.type !== 'stage' || (e.status || e.data?.status) !== 'pending'), event]);
                            } else if (event.type === "tool_call") {
                                // Handle both flat structure and legacy data wrapper
                                const toolName = event.tool || event.data?.tool || "tool";
                                const args = event.args || event.data?.args || {};
                                if (toolName === "web_search" || toolName === "google_search" || toolName === "web") {
                                    throttledSetAgentStatus(tChat("agent.searching", { query: args.query || "web" }));
                                } else {
                                    throttledSetAgentStatus(tChat("agent.executing", { tool: toolName }));
                                }
                                collectedEvents.push(event);
                                batchEventUpdate(event);
                            } else if (event.type === "tool_result") {
                                collectedEvents.push(event);
                                batchEventUpdate(event);
                            } else if (event.type === "routing") {
                                // Handle routing decision events
                                collectedEvents.push(event);
                                batchEventUpdate(event);
                            } else if (event.type === "handoff") {
                                // Handle agent handoff events
                                const target = event.target || "";
                                throttledSetAgentStatus(tChat("agent.handoffTo", { target }));
                                collectedEvents.push(event);
                                batchEventUpdate(event);
                            } else if (event.type === "source") {
                                // Handle source events from search
                                collectedEvents.push(event);
                                batchEventUpdate(event);
                            } else if (event.type === "code_result") {
                                // Handle code execution results
                                collectedEvents.push(event);
                                batchEventUpdate(event);
                            } else if (event.type === "visualization" && event.data && event.mime_type) {
                                // Handle visualization event from data analytics agent
                                const visualization = {
                                    data: event.data as string,
                                    mimeType: event.mime_type as "image/png" | "text/html",
                                };
                                collectedVisualizations.push(visualization);
                                setStreamingVisualizations(prev => [...prev, visualization]);
                                collectedEvents.push(event);
                            } else if (event.type === "error") {
                                fullContent = tChat("agent.error", { error: event.data });
                                updateStreamingContent(fullContent);
                            } else if (event.type === "complete") {
                                // Stream complete, break out of loop
                                break;
                            }
                        } catch (e) {
                            console.error("[SSE Parse Error]", e, "Line:", line);
                        }
                    } else if (line.startsWith("event: ")) {
                        // SSE event type line, can be ignored as we parse data lines
                        continue;
                    }
                }
            }

            if (fullContent) {
                const sanitizedContent = fullContent;
                await addMessage(conversationId, {
                    role: "assistant",
                    content: sanitizedContent,
                    metadata: (collectedEvents.length || collectedVisualizations.length) ? {
                        agentEvents: collectedEvents.length ? collectedEvents : undefined,
                        visualizations: collectedVisualizations.length ? collectedVisualizations : undefined,
                    } : undefined,
                });
            }
        } catch (error) {
            console.error("Agent task error:", error);
            await addMessage(conversationId, { role: "assistant", content: tChat("connectionError") });
        } finally {
            flushTokenBatch();
            setStreamingContent("");
            streamingContentRef.current = "";
            setAgentStatus(null);
            resetStreamingEvents();
            setStreamingVisualizations([]);
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

    // Use ref for stable callback reference
    const handleRegenerateRef = useRef<(messageId: string) => Promise<void>>();
    handleRegenerateRef.current = async (messageId: string) => {
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

    const handleRegenerate = useCallback((messageId: string) => {
        handleRegenerateRef.current?.(messageId);
    }, []);

    const handleVoiceTranscription = useCallback((text: string) => {
        // Append transcribed text to existing input, separated by space if needed
        setInput((prev) => {
            if (prev.trim()) {
                return `${prev.trim()} ${text}`;
            }
            return text;
        });
        // Focus the input after transcription
        inputRef.current?.focus();
    }, []);

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
    const hasMessages = messages.length > 0 || streamingContent || isLoading;

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
                        <MessageList
                            messages={messages}
                            streamingContent={streamingContent}
                            isLoading={isLoading}
                            agentStatus={agentStatus}
                            streamingEvents={streamingEvents}
                            streamingVisualizations={streamingVisualizations}
                            streamingStartTime={streamingStartTimeRef.current}
                            onRegenerate={handleRegenerate}
                            messagesEndRef={messagesEndRef}
                        />
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
                                className="flex items-center justify-center gap-4 mb-8 animate-slide-up"
                                style={{ animationDelay: '0.1s', animationFillMode: 'backwards' }}
                            >
                                <div className="relative w-14 h-14 flex items-center justify-center group">
                                    <div className="absolute inset-0 bg-gradient-to-br from-foreground/12 to-foreground/3 rounded-2xl blur-xl opacity-50 group-hover:opacity-100 transition-opacity duration-500" />
                                    <Image
                                        src="/images/logo-dark.svg"
                                        alt="HyperAgent"
                                        width={56}
                                        height={56}
                                        priority
                                        className="dark:hidden relative z-10 transition-all duration-300 group-hover:scale-110 group-hover:rotate-3"
                                    />
                                    <Image
                                        src="/images/logo-light.svg"
                                        alt="HyperAgent"
                                        width={56}
                                        height={56}
                                        priority
                                        className="hidden dark:block relative z-10 transition-all duration-300 group-hover:scale-110 group-hover:rotate-3"
                                    />
                                </div>
                                <h1 className="brand-title brand-title-lg">
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
                            "relative flex flex-col bg-card rounded-xl border border-border focus-within:border-foreground/30 focus-within:shadow-glow-sm transition-all duration-200"
                        )}>
                            {/* Attachment preview */}
                            <AttachmentPreview
                                attachments={attachments}
                                onRemove={removeAttachment}
                            />

                            {/* Main input row */}
                            <div className="flex items-end">
                                {/* Textarea */}
                                <textarea
                                    ref={inputRef}
                                    value={input}
                                    onChange={(e) => setInput(e.target.value)}
                                    placeholder={getPlaceholder()}
                                    className={cn(
                                        "flex-1 bg-transparent text-foreground placeholder:text-muted-foreground focus:outline-none leading-relaxed textarea-auto-resize",
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
                            </div>

                            {/* Bottom bar with plus button, voice input, hint and send button */}
                            <div className="flex items-center justify-between px-2 md:px-3 py-2 border-t border-border/50">
                                <div className="flex items-center gap-1">
                                    <FileUploadButton
                                        onFilesSelected={addFiles}
                                        onSourceSelect={handleSourceSelect}
                                        disabled={isProcessing || isUploading}
                                    />
                                    <VoiceInputButton
                                        onTranscription={handleVoiceTranscription}
                                        disabled={isProcessing || isUploading}
                                    />
                                    <p className="text-xs text-muted-foreground">
                                        {attachments.length > 0
                                            ? tChat("filesAttached", { count: attachments.length })
                                            : tChat("pressEnterToSend")}
                                    </p>
                                </div>
                                <button
                                    onClick={handleSubmit}
                                    disabled={!input.trim() || isProcessing || isUploading}
                                    className={cn(
                                        "px-4 py-2 rounded-xl transition-all duration-200 min-h-[44px] flex items-center justify-center gap-2 font-medium text-sm",
                                        input.trim() && !isProcessing && !isUploading
                                            ? "bg-primary text-primary-foreground hover:bg-primary/90 hover:shadow-glow-sm"
                                            : "bg-secondary text-muted-foreground"
                                    )}
                                >
                                    {isProcessing || isUploading ? (
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
                                                    "relative flex items-center gap-2 px-3 py-2 rounded-xl transition-all duration-200",
                                                    "text-sm font-medium",
                                                    isSelected
                                                        ? "bg-secondary text-foreground ring-1 ring-foreground/50 shadow-glow-sm"
                                                        : "bg-card text-muted-foreground border border-border hover:bg-secondary/50 hover:text-foreground hover:border-foreground/20"
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
                                                    <div className="bg-card border border-border rounded-xl overflow-hidden min-w-[220px] shadow-lg">
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
                                                                            "flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-xl text-xs font-medium transition-all duration-200",
                                                                            selectedDepth === depth
                                                                                ? "bg-foreground text-background shadow-glow-sm"
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
