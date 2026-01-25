"use client";

import React, { useState, useRef, useEffect, useCallback, memo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useSession } from "next-auth/react";
import { useTranslations, useLocale } from "next-intl";
import {
    Send,
    Square,
    GraduationCap,
    TrendingUp,
    Code2,
    Newspaper,
    BarChart3,
    Search,
    Check,
    Zap,
    Layers,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useChatStore } from "@/lib/stores/chat-store";
import { useAgentProgressStore } from "@/lib/stores/agent-progress-store";
import { MessageBubble } from "@/components/chat/message-bubble";
import { FileUploadButton } from "@/components/chat/file-upload-button";
import { VoiceInputButton } from "@/components/chat/voice-input-button";
import { AttachmentPreview } from "@/components/chat/attachment-preview";
import { Button } from "@/components/ui/button";
import { useFileUpload } from "@/lib/hooks/use-file-upload";
import { useGoogleDrivePicker } from "@/lib/hooks/use-google-drive-picker";
import type {
    AgentType,
    ResearchScenario,
    ResearchDepth,
    FileAttachment,
    Message,
    AgentEvent,
    GeneratedImage,
    Source,
    InterruptEvent,
    InterruptResponse,
} from "@/lib/types";
import { AskUserInput } from "@/components/hitl/ask-user-input";
import type { TimestampedEvent } from "@/lib/stores/agent-progress-store";
import {
    type StreamEvent,
    createStreamingContext,
    getEventKey,
    createTimestampedEvent,
    mergeTokenContent,
    parseSourceFromEvent,
    parseImageFromEvent,
    filterEventsForSaving,
    isSearchTool,
} from "@/lib/utils/streaming-helpers";

// Larger icons for better visual presence
const AGENT_KEYS = ["research", "data"] as const;
type VisibleAgent = (typeof AGENT_KEYS)[number];
const AGENT_ICONS: Record<VisibleAgent, React.ReactNode> = {
    research: <Search className="w-5 h-5" />,
    data: <BarChart3 className="w-5 h-5" />,
};

const SCENARIO_ICONS: Record<ResearchScenario, React.ReactNode> = {
    academic: <GraduationCap className="w-5 h-5" />,
    market: <TrendingUp className="w-5 h-5" />,
    technical: <Code2 className="w-5 h-5" />,
    news: <Newspaper className="w-5 h-5" />,
};

const SCENARIO_KEYS: ResearchScenario[] = ["academic", "market", "technical", "news"];
const DEPTH_KEYS: ResearchDepth[] = ["fast", "deep"];

const DEPTH_ICONS: Record<ResearchDepth, React.ReactNode> = {
    fast: <Zap className="w-4 h-4" />,
    deep: <Layers className="w-4 h-4" />,
};

// Memoized message list to prevent re-renders on input changes
interface MessageListProps {
    messages: Message[];
    streamingContent: string;
    isLoading: boolean;
    streamingImages: GeneratedImage[];
    streamingEvents: TimestampedEvent[];
    streamingSources: Source[];
    streamingAgentType?: string;
    streamingStartTime: Date;
    onRegenerate: (messageId: string) => void;
    messagesEndRef: React.RefObject<HTMLDivElement>;
    activeInterrupt?: InterruptEvent | null;
    onInterruptRespond?: (response: InterruptResponse) => void;
    onInterruptCancel?: () => void;
}

const MessageList = memo(function MessageList({
    messages,
    streamingContent,
    isLoading,
    streamingImages,
    streamingEvents,
    streamingSources,
    streamingAgentType,
    streamingStartTime,
    onRegenerate,
    messagesEndRef,
    activeInterrupt,
    onInterruptRespond,
    onInterruptCancel,
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
                        images={streamingImages}
                        streamingEvents={streamingEvents}
                        streamingSources={streamingSources}
                        agentType={streamingAgentType}
                    />
                </div>
            )}
            {/* Inline HITL Input */}
            {activeInterrupt && onInterruptRespond && onInterruptCancel && (
                <div className="animate-fade-in px-4 py-2">
                    <AskUserInput
                        key={activeInterrupt.interrupt_id}
                        interrupt={activeInterrupt}
                        onRespond={onInterruptRespond}
                        onCancel={onInterruptCancel}
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
    const locale = useLocale();
    const t = useTranslations("home");
    const tAgents = useTranslations("agents");
    const tResearch = useTranslations("research");
    const tChat = useTranslations("chat");
    const tTools = useTranslations("chat.agent.tools");

    // Helper to get translated tool name
    const getTranslatedToolName = useCallback((toolName: string): string => {
        const toolKey = toolName.toLowerCase();
        switch (toolKey) {
            case "web_search":
                return tTools("web_search");
            case "google_search":
                return tTools("google_search");
            case "web":
                return tTools("web");
            case "generate_image":
                return tTools("generate_image");
            case "analyze_image":
                return tTools("analyze_image");
            case "execute_code":
                return tTools("execute_code");
            case "sandbox_file":
                return tTools("sandbox_file");
            case "browser_use":
                return tTools("browser_use");
            case "browser_navigate":
                return tTools("browser_navigate");
            default:
                return tTools("default");
        }
    }, [tTools]);
    const [input, setInput] = useState("");
    const [selectedAgent, setSelectedAgent] = useState<AgentType | null>(null);
    const [selectedScenario, setSelectedScenario] = useState<ResearchScenario | null>(null);
    const [selectedDepth, setSelectedDepth] = useState<ResearchDepth>("fast");
    const [showResearchSubmenu, setShowResearchSubmenu] = useState(false);
    const [submenuPosition, setSubmenuPosition] = useState<{ x: 'left' | 'right'; y: 'top' | 'bottom' }>({ x: 'right', y: 'bottom' });
    const submenuRef = useRef<HTMLDivElement>(null);
    const [streamingContent, setStreamingContent] = useState("");
    const [streamingImages, setStreamingImages] = useState<GeneratedImage[]>([]);
    const [streamingEvents, setStreamingEvents] = useState<TimestampedEvent[]>([]);
    const [streamingSources, setStreamingSources] = useState<Source[]>([]);
    const [streamingAgentType, setStreamingAgentType] = useState<string | undefined>(undefined);
    const [activeInterrupt, setActiveInterrupt] = useState<InterruptEvent | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);
    const researchRef = useRef<HTMLDivElement>(null);
    const streamingContentRef = useRef("");
    const updateScheduledRef = useRef(false);
    const streamingStartTimeRef = useRef<Date>(new Date());
    const abortControllerRef = useRef<AbortController | null>(null);

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

    // Throttled streaming content update using requestAnimationFrame with batching
    const updateStreamingContent = useCallback((content: string) => {
        // Only update if content actually changed
        if (streamingContentRef.current === content) return;
        streamingContentRef.current = content;
        
        // Cancel any pending update to prevent multiple queued updates
        if (updateScheduledRef.current) return;
        
        updateScheduledRef.current = true;
        // Use requestAnimationFrame for smooth updates
        requestAnimationFrame(() => {
            updateScheduledRef.current = false;
            const currentContent = streamingContentRef.current;
            // Only set state if content actually changed to prevent unnecessary updates
            setStreamingContent(prev => {
                // Prevent unnecessary updates that could cause loops
                if (prev === currentContent) return prev;
                return currentContent;
            });
        });
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

    // Dynamic positioning for research submenu
    useEffect(() => {
        if (!showResearchSubmenu || !submenuRef.current || !researchRef.current) return;

        const calculatePosition = () => {
            const button = researchRef.current!.getBoundingClientRect();
            const submenu = submenuRef.current!.getBoundingClientRect();
            const viewport = {
                width: window.innerWidth,
                height: window.innerHeight,
            };

            // Calculate available space in each direction
            const spaceRight = viewport.width - button.right;
            const spaceLeft = button.left;
            const spaceBottom = viewport.height - button.bottom;
            const spaceTop = button.top;

            // Determine horizontal position (prefer right, fall back to left)
            const x: 'left' | 'right' = spaceRight >= submenu.width ? 'right' :
                                        spaceLeft >= submenu.width ? 'left' : 'right';

            // Determine vertical position (prefer bottom, fall back to top)
            const y: 'top' | 'bottom' = spaceBottom >= submenu.height + 12 ? 'bottom' :
                                        spaceTop >= submenu.height + 12 ? 'top' : 'bottom';

            setSubmenuPosition({ x, y });
        };

        // Calculate immediately
        calculatePosition();

        // Recalculate on scroll/resize
        const handleReposition = () => calculatePosition();
        window.addEventListener('scroll', handleReposition, true);
        window.addEventListener('resize', handleReposition);

        return () => {
            window.removeEventListener('scroll', handleReposition, true);
            window.removeEventListener('resize', handleReposition);
        };
    }, [showResearchSubmenu]);

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

    const activeConversationId = useChatStore((state) => state.activeConversationId);
    const isLoading = useChatStore((state) => state.isLoading);
    const hasHydrated = useChatStore((state) => state.hasHydrated);
    const setLoading = useChatStore((state) => state.setLoading);
    const setStreaming = useChatStore((state) => state.setStreaming);
    const addMessage = useChatStore((state) => state.addMessage);
    const removeMessage = useChatStore((state) => state.removeMessage);
    const createConversation = useChatStore((state) => state.createConversation);
    const getActiveConversation = useChatStore((state) => state.getActiveConversation);
    const loadConversation = useChatStore((state) => state.loadConversation);
    const conversations = useChatStore((state) => state.conversations);

    // Agent progress store for sidebar visibility
    const {
        startProgress: startAgentProgress,
        addEvent: addAgentEvent,
        updateStage: updateAgentStage,
        endProgress: endAgentProgress,
        clearProgress: clearAgentProgress,
        setBrowserStream,
        activeProgress,
    } = useAgentProgressStore();

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

    // Clear agent progress when switching to a different conversation or page
    // This ensures the progress panel only shows progress for the current conversation
    useEffect(() => {
        if (!hasHydrated) return;
        if (!activeProgress) return;

        // Check if the progress belongs to a different conversation
        const progressBelongsToDifferentConversation =
            activeProgress.conversationId !== null &&
            activeProgress.conversationId !== activeConversationId;

        // Check if we navigated away from conversations entirely (no active conversation)
        const navigatedAwayFromConversations =
            !activeConversationId && activeProgress.conversationId !== null;

        if (progressBelongsToDifferentConversation || navigatedAwayFromConversations) {
            // Only clear if the progress is completed (not currently streaming)
            // If still streaming, the user might want to see it finish
            if (!activeProgress.isStreaming) {
                clearAgentProgress();
            }
        }
    }, [activeConversationId, hasHydrated, activeProgress, clearAgentProgress]);

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

    const handleStop = useCallback(async () => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
        }
        // Immediately reset UI state
        flushTokenBatch();
        const partialContent = streamingContentRef.current;
        setStreamingContent("");
        streamingContentRef.current = "";
        setStreamingImages([]);
        setStreamingEvents([]);
        setStreamingSources([]);
        setActiveInterrupt(null);
        setLoading(false);
        setStreaming(false);
        endAgentProgress();

        // Add cancelled message to conversation
        if (activeConversationId) {
            const cancelledMessage = partialContent
                ? `${partialContent}\n\n---\n\n*${tChat("requestCancelled")}*`
                : `*${tChat("requestCancelled")}*`;
            await addMessage(activeConversationId, {
                role: "assistant",
                content: cancelledMessage,
            });
        }
    }, [flushTokenBatch, setLoading, setStreaming, endAgentProgress, activeConversationId, addMessage, tChat]);

    const handleSubmit = async () => {
        if (!input.trim() || isLoading || isUploading) return;

        const userMessage = input.trim();
        const attachmentIds = getUploadedFileIds();
        const messageAttachments = attachments.filter(a => a.status === 'uploaded');
        setInput("");
        clearAttachments();

        if (selectedAgent === "research" && selectedScenario) {
            handleResearch(userMessage);
        } else if (selectedAgent === "data") {
            await handleAgentTask(userMessage, selectedAgent, attachmentIds, messageAttachments);
        } else if (!selectedAgent && activeConversation?.type === "data") {
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
        // Clear inline streaming state
        setStreamingImages([]);
        setStreamingEvents([]);
        setStreamingSources([]);
        setStreamingAgentType("chat");

        let conversationId = activeConversationId;
        if (!conversationId || activeConversation?.type !== "chat") {
            conversationId = await createConversation("chat");
        }

        // Get conversation messages for context BEFORE adding the new message
        // The backend will add the current message separately
        // Use getActiveConversation() to get fresh state, not cached activeConversation
        const conversationForHistory =
            conversations.find((conversation) => conversation.id === conversationId) || getActiveConversation();
        const conversationMessages = conversationForHistory?.messages || [];
        const history = conversationMessages
            .filter(msg => msg.role === "user" || msg.role === "assistant")
            .map(msg => ({
                role: msg.role,
                content: msg.content,
                metadata: msg.metadata || null,
            }));

        // Debug: Log conversation history being sent
        console.log('[Chat] Sending request with history:', {
            conversationId,
            messageCount: conversationMessages.length,
            historyCount: history.length,
            historyPreview: history.slice(-3).map(m => ({ role: m.role, content: m.content.substring(0, 30) }))
        });

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

        // Start agent progress for sidebar visibility
        startAgentProgress(conversationId, "chat");

        // Add initial thinking event immediately for instant feedback
        const thinkingEvent: AgentEvent = {
            type: "stage",
            name: "thinking",
            description: tChat("agent.thinking"),
            status: "running",
        };
        addAgentEvent(thinkingEvent);

        // Initialize streaming context for tracking collected data
        const ctx = createStreamingContext(thinkingEvent);

        // Helper to merge token content and update UI
        const handleTokenContent = (tokenContent: string): void => {
            ctx.fullContent = mergeTokenContent(ctx.fullContent, tokenContent);
            updateStreamingContent(ctx.fullContent);
        };

        // Helper to add event and update streaming state (with deduplication)
        const addStreamingEvent = (event: AgentEvent): void => {
            const eventKey = getEventKey(event);
            if (ctx.seenEventKeys.has(eventKey)) return;
            ctx.seenEventKeys.add(eventKey);

            addAgentEvent(event);
            setStreamingEvents(prev => [...prev, createTimestampedEvent(event)]);
            ctx.collectedEvents.push(event);
        };

        // Helper to add source and update streaming state
        const addStreamingSource = (source: Source): void => {
            ctx.collectedSources.push(source);
            setStreamingSources(prev => [...prev, source]);
        };

        try {
            // Create new abort controller for this request
            abortControllerRef.current = new AbortController();

            const response = await fetch("/api/v1/query/stream", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: 'include',
                signal: abortControllerRef.current.signal,
                body: JSON.stringify({
                    message: userMessage,
                    mode: "chat",
                    attachment_ids: combinedAttachmentIds,
                    // Always send conversation_id (even for local conversations) to enable sandbox reuse
                    // Backend uses it as task_id for e2b sandbox session management
                    conversation_id: conversationId,
                    history: history,
                    locale: locale,
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
                            const event = JSON.parse(jsonStr) as StreamEvent;

                            if (event.type === "token" && (event.data || event.content)) {
                                const tokenContent = (typeof event.data === "string" ? event.data : event.content) || "";
                                handleTokenContent(tokenContent);
                            } else if (event.type === "stage") {
                                flushTokenBatch();
                                const eventData = typeof event.data === "object" && event.data !== null ? event.data : null;
                                const stageDescription = event.description || eventData?.description || null;
                                updateAgentStage(stageDescription);
                                addStreamingEvent(event);
                            } else if (event.type === "tool_call") {
                                const eventData = typeof event.data === "object" && event.data !== null ? event.data : null;
                                const toolName = event.tool || eventData?.tool || "web";
                                const args = event.args || eventData?.args || {};
                                const rawQuery = typeof args === "object" && args !== null ? (args as Record<string, unknown>).query : undefined;
                                const queryArg = typeof rawQuery === "string" ? rawQuery : "web";
                                if (isSearchTool(toolName)) {
                                    updateAgentStage(tChat("agent.searching", { query: queryArg }));
                                } else {
                                    updateAgentStage(tChat("agent.executing", { tool: getTranslatedToolName(toolName) }));
                                }
                                addStreamingEvent(event);
                            } else if (event.type === "tool_result") {
                                // Debug: Log tool results for app preview debugging
                                const tool = event.tool || (event.data as any)?.tool;
                                if (tool === "app_start_server" || tool === "app_get_preview_url" || tool === "invoke_skill") {
                                    console.log("[DEBUG] Tool result for app preview:", {
                                        tool,
                                        hasContent: !!event.content,
                                        contentPreview: typeof event.content === "string" ? event.content.substring(0, 200) : event.content
                                    });
                                }
                                addStreamingEvent(event);
                            } else if (event.type === "routing") {
                                addStreamingEvent(event);
                            } else if (event.type === "handoff") {
                                const target = event.target || "";
                                updateAgentStage(tChat("agent.handoffTo", { target }));
                                addStreamingEvent(event);
                            } else if (event.type === "source") {
                                addStreamingEvent(event);
                                const newSource = parseSourceFromEvent(event, ctx.collectedSources.length);
                                if (newSource) {
                                    addStreamingSource(newSource);
                                }
                            } else if (event.type === "code_result") {
                                addStreamingEvent(event);
                            } else if (event.type === "image") {
                                const imageData = parseImageFromEvent(event, ctx.collectedImages.length);
                                if (imageData) {
                                    const isDuplicate = ctx.collectedImages.some(img => img.index === imageData.index);
                                    if (!isDuplicate) {
                                        ctx.collectedImages.push(imageData);
                                        setStreamingImages(prev => [...prev, imageData]);
                                        ctx.collectedEvents.push(event);
                                    }
                                }
                            } else if (event.type === "browser_stream") {
                                // Handle browser stream event - show live browser view
                                const streamUrl = event.stream_url as string;
                                const sandboxId = event.sandbox_id as string;
                                if (streamUrl && sandboxId) {
                                    console.log("[Browser Stream] Received:", { streamUrl, sandboxId });
                                    setBrowserStream({
                                        streamUrl,
                                        sandboxId,
                                    });
                                    addAgentEvent(event);
                                }
                            } else if (event.type === "browser_action") {
                                // Handle browser action events - sync progress with browser stream
                                const action = event.action as string;
                                const description = event.description as string;
                                const target = event.target as string | undefined;
                                const status = (event.status as string) || "running";
                                // Transform to stage event for progress display
                                const browserStageEvent: AgentEvent = {
                                    type: "stage",
                                    name: `browser_${action}`,
                                    description: target ? `${description}: ${target}` : description,
                                    status: status === "completed" ? "completed" : "running",
                                };
                                addStreamingEvent(browserStageEvent);
                            } else if (event.type === "skill_output") {
                                // Handle skill output events
                                const skillId = event.skill_id as string;
                                // Debug: Log skill output for app preview debugging
                                if (skillId === "app_builder") {
                                    const output = event.output as any;
                                    console.log("[DEBUG] App builder skill output:", {
                                        hasOutput: !!output,
                                        hasPreviewUrl: !!output?.preview_url,
                                        previewUrl: output?.preview_url,
                                        template: output?.template
                                    });
                                }
                                addStreamingEvent(event);
                                updateAgentStage(tChat("agent.skillCompleted", { skill: skillId }));
                            } else if (event.type === "interrupt") {
                                const interruptEvent: InterruptEvent = {
                                    type: "interrupt",
                                    interrupt_id: event.interrupt_id as string,
                                    interrupt_type: event.interrupt_type as InterruptEvent["interrupt_type"],
                                    title: event.title as string,
                                    message: event.message as string,
                                    options: event.options,
                                    tool_info: event.tool_info,
                                    default_action: event.default_action,
                                    timeout_seconds: (event.timeout_seconds as number) || 120,
                                    timestamp: (event.timestamp as number | undefined) ?? Date.now(),
                                };
                                console.log("[HITL] Interrupt received:", {
                                    interrupt_id: interruptEvent.interrupt_id,
                                    message: interruptEvent.message?.substring(0, 50),
                                    timestamp: interruptEvent.timestamp,
                                });
                                setActiveInterrupt((prev) => {
                                    console.log("[HITL] Setting interrupt, prev:", prev?.interrupt_id, "new:", interruptEvent.interrupt_id);
                                    return interruptEvent;
                                });
                                addStreamingEvent(event);
                            } else if (event.type === "error") {
                                const errorData = typeof event.data === "string" ? event.data : "Unknown error";
                                ctx.fullContent = tChat("agent.error", { error: errorData });
                                updateStreamingContent(ctx.fullContent);
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

            if (ctx.fullContent || ctx.collectedImages.length > 0) {
                // Clear streaming state BEFORE saving to prevent duplicate rendering
                flushTokenBatch();
                setStreamingContent("");
                streamingContentRef.current = "";
                setStreamingImages([]);
                setStreamingEvents([]);
                setStreamingSources([]);
                setLoading(false);

                const savedEvents = filterEventsForSaving(ctx.collectedEvents);

                await addMessage(conversationId, {
                    role: "assistant",
                    content: ctx.fullContent,
                    metadata: {
                        ...(ctx.collectedImages.length ? { images: ctx.collectedImages } : {}),
                        ...(savedEvents.length ? { agentEvents: savedEvents } : {}),
                    },
                });
            }
        } catch (error) {
            if (error instanceof Error && error.name === 'AbortError') {
                console.log("Chat request cancelled by user");
            } else {
                console.error("Chat error:", error);
                await addMessage(conversationId, { role: "assistant", content: tChat("connectionError") });
            }
        } finally {
            // Ensure cleanup in case of early exit
            abortControllerRef.current = null;
            flushTokenBatch();
            setStreamingContent("");
            streamingContentRef.current = "";
            setStreamingImages([]);
            setStreamingEvents([]);
            setStreamingSources([]);
            setLoading(false);
            setStreaming(false);
            endAgentProgress();
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
        // Clear inline streaming state
        setStreamingImages([]);
        setStreamingEvents([]);
        setStreamingSources([]);
        setStreamingAgentType(agentType);

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
        // Use getActiveConversation() to get fresh state, not cached activeConversation
        const conversationForHistory =
            conversations.find((conversation) => conversation.id === conversationId) || getActiveConversation();
        const conversationMessages = conversationForHistory?.messages || [];
        const history = conversationMessages
            .filter(msg => msg.role === "user" || msg.role === "assistant")
            .map(msg => ({
                role: msg.role,
                content: msg.content,
                metadata: msg.metadata || null,
            }));

        // Debug: Log conversation history being sent
        console.log('[Chat] Sending request with history:', {
            conversationId,
            messageCount: conversationMessages.length,
            historyCount: history.length,
            historyPreview: history.slice(-3).map(m => ({ role: m.role, content: m.content.substring(0, 30) }))
        });

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

        // Start agent progress for sidebar visibility
        startAgentProgress(conversationId, agentType);

        // Add initial thinking event immediately for instant feedback
        const thinkingEvent: AgentEvent = {
            type: "stage",
            name: "thinking",
            description: tChat("agent.thinking"),
            status: "running",
        };
        addAgentEvent(thinkingEvent);

        // Initialize streaming context for tracking collected data
        const ctx = createStreamingContext(thinkingEvent);

        // Helper to merge token content and update UI
        const handleTokenContent = (tokenContent: string): void => {
            ctx.fullContent = mergeTokenContent(ctx.fullContent, tokenContent);
            updateStreamingContent(ctx.fullContent);
        };

        // Helper to add event and update streaming state (with deduplication)
        const addStreamingEvent = (event: AgentEvent): void => {
            const eventKey = getEventKey(event);
            if (ctx.seenEventKeys.has(eventKey)) return;
            ctx.seenEventKeys.add(eventKey);

            addAgentEvent(event);
            setStreamingEvents(prev => [...prev, createTimestampedEvent(event)]);
            ctx.collectedEvents.push(event);
        };

        // Helper to add source and update streaming state
        const addStreamingSource = (source: Source): void => {
            ctx.collectedSources.push(source);
            setStreamingSources(prev => [...prev, source]);
        };

        try {
            // Create new abort controller for this request
            abortControllerRef.current = new AbortController();

            const response = await fetch("/api/v1/query/stream", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: 'include',
                signal: abortControllerRef.current.signal,
                body: JSON.stringify({
                    message: userMessage,
                    mode: agentType,
                    attachment_ids: combinedAttachmentIds,
                    // Always send conversation_id (even for local conversations) to enable sandbox reuse
                    // Backend uses it as task_id for e2b sandbox session management
                    conversation_id: conversationId,
                    history: history,
                    locale: locale,
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
                            const event = JSON.parse(jsonStr) as StreamEvent;

                            if (event.type === "token" && (event.data || event.content)) {
                                const tokenContent = (typeof event.data === "string" ? event.data : event.content) || "";
                                handleTokenContent(tokenContent);
                            } else if (event.type === "stage") {
                                flushTokenBatch();
                                const eventData = typeof event.data === "object" && event.data !== null ? event.data : null;
                                const stageDescription = event.description || eventData?.description || null;
                                updateAgentStage(stageDescription);
                                addStreamingEvent(event);
                            } else if (event.type === "tool_call") {
                                const eventData = typeof event.data === "object" && event.data !== null ? event.data : null;
                                const toolName = event.tool || eventData?.tool || "tool";
                                const args = event.args || eventData?.args || {};
                                const rawQuery = typeof args === "object" && args !== null ? (args as Record<string, unknown>).query : undefined;
                                const queryArg = typeof rawQuery === "string" ? rawQuery : "web";
                                if (isSearchTool(toolName)) {
                                    updateAgentStage(tChat("agent.searching", { query: queryArg }));
                                } else {
                                    updateAgentStage(tChat("agent.executing", { tool: getTranslatedToolName(toolName) }));
                                }
                                addStreamingEvent(event);
                            } else if (event.type === "tool_result") {
                                // Debug: Log tool results for app preview debugging
                                const tool = event.tool || (event.data as any)?.tool;
                                if (tool === "app_start_server" || tool === "app_get_preview_url" || tool === "invoke_skill") {
                                    console.log("[DEBUG] Tool result for app preview:", {
                                        tool,
                                        hasContent: !!event.content,
                                        contentPreview: typeof event.content === "string" ? event.content.substring(0, 200) : event.content
                                    });
                                }
                                addStreamingEvent(event);
                            } else if (event.type === "routing") {
                                addStreamingEvent(event);
                            } else if (event.type === "handoff") {
                                const target = event.target || "";
                                updateAgentStage(tChat("agent.handoffTo", { target }));
                                addStreamingEvent(event);
                            } else if (event.type === "source") {
                                addStreamingEvent(event);
                                const newSource = parseSourceFromEvent(event, ctx.collectedSources.length);
                                if (newSource) {
                                    addStreamingSource(newSource);
                                }
                            } else if (event.type === "code_result") {
                                addStreamingEvent(event);
                            } else if (event.type === "image") {
                                const imageData = parseImageFromEvent(event, ctx.collectedImages.length);
                                if (imageData) {
                                    const isDuplicate = ctx.collectedImages.some(img => img.index === imageData.index);
                                    if (!isDuplicate) {
                                        ctx.collectedImages.push(imageData);
                                        setStreamingImages(prev => [...prev, imageData]);
                                        ctx.collectedEvents.push(event);
                                    }
                                }
                            } else if (event.type === "browser_stream") {
                                // Handle browser stream event - show live browser view
                                const streamUrl = event.stream_url as string;
                                const sandboxId = event.sandbox_id as string;
                                const authKey = event.auth_key as string | undefined;
                                if (streamUrl && sandboxId) {
                                    console.log("[Browser Stream] Received:", { streamUrl, sandboxId });
                                    setBrowserStream({
                                        streamUrl,
                                        sandboxId,
                                        authKey,
                                    });
                                    addAgentEvent(event);
                                }
                            } else if (event.type === "browser_action") {
                                // Handle browser action events - sync progress with browser stream
                                const action = event.action as string;
                                const description = event.description as string;
                                const target = event.target as string | undefined;
                                const status = (event.status as string) || "running";
                                // Transform to stage event for progress display
                                const browserStageEvent: AgentEvent = {
                                    type: "stage",
                                    name: `browser_${action}`,
                                    description: target ? `${description}: ${target}` : description,
                                    status: status === "completed" ? "completed" : "running",
                                };
                                addStreamingEvent(browserStageEvent);
                            } else if (event.type === "skill_output") {
                                // Handle skill output events
                                const skillId = event.skill_id as string;
                                // Debug: Log skill output for app preview debugging
                                if (skillId === "app_builder") {
                                    const output = event.output as any;
                                    console.log("[DEBUG] App builder skill output:", {
                                        hasOutput: !!output,
                                        hasPreviewUrl: !!output?.preview_url,
                                        previewUrl: output?.preview_url,
                                        template: output?.template
                                    });
                                }
                                addStreamingEvent(event);
                                updateAgentStage(tChat("agent.skillCompleted", { skill: skillId }));
                            } else if (event.type === "interrupt") {
                                const interruptEvent: InterruptEvent = {
                                    type: "interrupt",
                                    interrupt_id: event.interrupt_id as string,
                                    interrupt_type: event.interrupt_type as InterruptEvent["interrupt_type"],
                                    title: event.title as string,
                                    message: event.message as string,
                                    options: event.options,
                                    tool_info: event.tool_info,
                                    default_action: event.default_action,
                                    timeout_seconds: (event.timeout_seconds as number) || 120,
                                    timestamp: (event.timestamp as number | undefined) ?? Date.now(),
                                };
                                console.log("[HITL] Interrupt received:", {
                                    interrupt_id: interruptEvent.interrupt_id,
                                    message: interruptEvent.message?.substring(0, 50),
                                    timestamp: interruptEvent.timestamp,
                                });
                                setActiveInterrupt((prev) => {
                                    console.log("[HITL] Setting interrupt, prev:", prev?.interrupt_id, "new:", interruptEvent.interrupt_id);
                                    return interruptEvent;
                                });
                                addStreamingEvent(event);
                            } else if (event.type === "error") {
                                const errorData = typeof event.data === "string" ? event.data : "Unknown error";
                                ctx.fullContent = tChat("agent.error", { error: errorData });
                                updateStreamingContent(ctx.fullContent);
                                addAgentEvent(event);
                            } else if (event.type === "complete") {
                                break;
                            }
                        } catch (e) {
                            console.error("[SSE Parse Error]", e, "Line:", line);
                        }
                    } else if (line.startsWith("event: ")) {
                        continue;
                    }
                }
            }

            if (ctx.fullContent || ctx.collectedImages.length > 0) {
                // Clear streaming state BEFORE saving to prevent duplicate rendering
                flushTokenBatch();
                setStreamingContent("");
                streamingContentRef.current = "";
                setStreamingImages([]);
                setStreamingEvents([]);
                setStreamingSources([]);
                setLoading(false);

                const savedEvents = filterEventsForSaving(ctx.collectedEvents);

                await addMessage(conversationId, {
                    role: "assistant",
                    content: ctx.fullContent,
                    metadata: {
                        ...(ctx.collectedImages.length ? { images: ctx.collectedImages } : {}),
                        ...(savedEvents.length ? { agentEvents: savedEvents } : {}),
                    },
                });
            }
        } catch (error) {
            if (error instanceof Error && error.name === 'AbortError') {
                console.log("Agent task cancelled by user");
            } else {
                console.error("Agent task error:", error);
                await addMessage(conversationId, { role: "assistant", content: tChat("connectionError") });
            }
        } finally {
            // Ensure cleanup in case of early exit
            abortControllerRef.current = null;
            flushTokenBatch();
            setStreamingContent("");
            streamingContentRef.current = "";
            setStreamingImages([]);
            setStreamingEvents([]);
            setStreamingSources([]);
            setLoading(false);
            setStreaming(false);
            endAgentProgress();
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
        let userMessageAttachments: FileAttachment[] = [];
        for (let i = messageIndex - 1; i >= 0; i--) {
            if (messages[i].role === "user") {
                userMessage = messages[i].content;
                userMessageAttachments = messages[i].attachments || [];
                break;
            }
        }
        if (!userMessage) return;

        const attachmentIds = userMessageAttachments.filter(a => a.status === 'uploaded').map(a => a.id);
        removeMessage(activeConversationId, messageId);

        // Check conversation type and call the appropriate handler
        const conversationType = activeConversation?.type;
        if (conversationType === "data") {
            await handleAgentTask(userMessage, conversationType as AgentType, attachmentIds, userMessageAttachments);
        } else {
            // For chat type, use handleChat
            await handleChat(userMessage, true, attachmentIds, userMessageAttachments);
        }
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

    // Handle interrupt response (HITL)
    const handleInterruptResponse = useCallback(async (response: InterruptResponse) => {
        if (!activeInterrupt) {
            console.warn("[HITL] No active interrupt to respond to");
            return;
        }

        // Store the interrupt ID we're responding to
        const respondingToInterruptId = response.interrupt_id;
        console.log("[HITL] Submitting response:", response);

        try {
            // Get the thread ID - use task_id or conversation_id
            const threadId = activeConversationId || "default";

            // Submit response to backend
            const res = await fetch(`/api/v1/hitl/respond/${threadId}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
                body: JSON.stringify(response),
            });

            const result = await res.json();
            console.log("[HITL] Response result:", result);

            if (!res.ok) {
                console.error("[HITL] Server error:", result);
            }
        } catch (error) {
            console.error("[HITL] Failed to submit response:", error);
        } finally {
            // Only clear if we're still showing the SAME interrupt we responded to
            // A new interrupt may have arrived while we were submitting the response
            setActiveInterrupt((current) => {
                if (current?.interrupt_id === respondingToInterruptId) {
                    console.log("[HITL] Clearing interrupt:", respondingToInterruptId);
                    return null;
                }
                console.log("[HITL] New interrupt arrived, keeping:", current?.interrupt_id);
                return current;
            });
        }
    }, [activeInterrupt, activeConversationId]);

    // Handle interrupt cancellation
    const handleInterruptCancel = useCallback(() => {
        if (!activeInterrupt) return;

        // Submit cancel response
        handleInterruptResponse({
            interrupt_id: activeInterrupt.interrupt_id,
            action: "cancel",
        });
    }, [activeInterrupt, handleInterruptResponse]);

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
                            streamingImages={streamingImages}
                            streamingEvents={streamingEvents}
                            streamingSources={streamingSources}
                            streamingAgentType={streamingAgentType}
                            streamingStartTime={streamingStartTimeRef.current}
                            onRegenerate={handleRegenerate}
                            messagesEndRef={messagesEndRef}
                            activeInterrupt={activeInterrupt}
                            onInterruptRespond={handleInterruptResponse}
                            onInterruptCancel={handleInterruptCancel}
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
                        <div className="text-center mb-6">
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
                            "relative flex flex-col bg-card rounded-2xl border border-border focus-within:border-foreground/30 transition-colors"
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

                            {/* Bottom bar with plus button, voice input, model selector, hint and send button */}
                            <div className="flex items-center justify-between px-2 md:px-3 py-2 border-t border-border/50">
                                <div className="flex items-center gap-2">
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
                                    </div>
                                    <p className="text-xs text-muted-foreground">
                                        {attachments.length > 0
                                            ? tChat("filesAttached", { count: attachments.length })
                                            : tChat("pressEnterToSend")}
                                    </p>
                                </div>
                                <Button
                                    onClick={isProcessing ? handleStop : handleSubmit}
                                    disabled={isUploading || (!isProcessing && !input.trim())}
                                    variant={isProcessing ? "destructive" : (input.trim() && !isUploading ? "primary" : "default")}
                                    size="icon"
                                >
                                    {isProcessing ? (
                                        <Square className="w-4 h-4 fill-current" />
                                    ) : (
                                        <Send className="w-4 h-4" />
                                    )}
                                </Button>
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
                                                    "text-sm font-medium border",
                                                    isSelected
                                                        ? "bg-foreground text-background border-foreground"
                                                        : "bg-card text-muted-foreground border-border hover:bg-secondary hover:text-foreground"
                                                )}
                                            >
                                                {/* Selection checkmark */}
                                                {isSelected && (
                                                    <span className="flex items-center justify-center w-4 h-4 rounded-full bg-background text-foreground">
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
                                                    <span className="text-xs opacity-70">
                                                        · {tResearch(`${selectedScenario}.name`)} · {tResearch(`depth.${selectedDepth}.name`)}
                                                    </span>
                                                )}
                                            </button>

                                            {/* Research scenarios submenu */}
                                            {agent === "research" && showResearchSubmenu && (
                                                <>
                                                    {/* Backdrop for dismissal */}
                                                    <div className="fixed inset-0 z-40" onClick={() => setShowResearchSubmenu(false)} />

                                                    <div
                                                        ref={submenuRef}
                                                        className={cn(
                                                            "absolute z-50 transition-colors",
                                                            submenuPosition.x === 'right' ? 'left-0' : 'right-0',
                                                            submenuPosition.y === 'bottom' ? 'top-full mt-3' : 'bottom-full mb-3'
                                                        )}
                                                        onMouseLeave={() => setShowResearchSubmenu(false)}
                                                    >
                                                        {/* Arrow pointer */}
                                                        <div className={cn(
                                                            "absolute w-3 h-3 rotate-45 bg-card border border-border transition-colors",
                                                            submenuPosition.y === 'bottom' ? '-top-1.5 border-l border-t' : '-bottom-1.5 border-r border-b',
                                                            submenuPosition.x === 'right' ? 'left-6' : 'right-6'
                                                        )} />

                                                        <div className="relative bg-card border border-border rounded-xl overflow-hidden w-[280px]"
                                                             style={{ maxWidth: 'min(280px, calc(100vw - 2rem))' }}
                                                        >
                                                        {/* Scenarios section */}
                                                        <div className="p-3">
                                                            <div className="grid grid-cols-2 gap-2">
                                                                {SCENARIO_KEYS.map((scenario) => (
                                                                    <button
                                                                        key={scenario}
                                                                        onClick={() => handleScenarioSelect(scenario)}
                                                                        className={cn(
                                                                            "flex flex-col items-center gap-2 p-3 rounded-lg transition-colors",
                                                                            "border border-border",
                                                                            selectedScenario === scenario
                                                                                ? "bg-foreground text-background"
                                                                                : "bg-card text-muted-foreground hover:bg-secondary hover:text-foreground"
                                                                        )}
                                                                    >
                                                                        <span className={cn(
                                                                            "flex items-center justify-center w-9 h-9 rounded-lg transition-colors",
                                                                            selectedScenario === scenario
                                                                                ? "bg-background text-foreground"
                                                                                : "bg-secondary text-muted-foreground"
                                                                        )}>
                                                                            {SCENARIO_ICONS[scenario]}
                                                                        </span>
                                                                        <span className="text-xs font-medium text-center leading-tight">
                                                                            {tResearch(`${scenario}.name`)}
                                                                        </span>
                                                                    </button>
                                                                ))}
                                                            </div>
                                                        </div>

                                                        {/* Depth selector */}
                                                        <div className="border-t border-border bg-secondary px-3 py-3">
                                                            <div className="flex items-center justify-between gap-3">
                                                                <span className="text-xs font-medium text-muted-foreground">
                                                                    {tResearch("depth.label")}
                                                                </span>
                                                                <div className="flex gap-1.5">
                                                                    {DEPTH_KEYS.map((depth) => (
                                                                        <button
                                                                            key={depth}
                                                                            onClick={(e) => {
                                                                                e.stopPropagation();
                                                                                setSelectedDepth(depth);
                                                                            }}
                                                                            className={cn(
                                                                                "flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors",
                                                                                "border border-border",
                                                                                selectedDepth === depth
                                                                                    ? "bg-foreground text-background"
                                                                                    : "bg-card text-muted-foreground hover:bg-muted hover:text-foreground"
                                                                            )}
                                                                        >
                                                                            {DEPTH_ICONS[depth]}
                                                                            <span>{tResearch(`depth.${depth}.name`)}</span>
                                                                        </button>
                                                                    ))}
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </div>
                                                    </div>
                                                </>
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
