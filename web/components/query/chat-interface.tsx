"use client";

import React, { useState, useRef, useEffect, useCallback, memo, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useSession } from "next-auth/react";
import { useTranslations, useLocale } from "next-intl";
import { useChatStore } from "@/lib/stores/chat-store";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { useAgentProgressStore } from "@/lib/stores/agent-progress-store";
import { useExecutionProgressStore } from "@/lib/stores/execution-progress-store";
import { useComputerStore } from "@/lib/stores/computer-store";

import { MessageBubble } from "@/components/chat/message-bubble";
import { useFileUpload } from "@/lib/hooks/use-file-upload";
import { useGoogleDrivePicker } from "@/lib/hooks/use-google-drive-picker";
import type {
    AgentType,
    ResearchScenario,
    ResearchDepth,
    FileAttachment,
    Message,
    AgentEvent,
    Source,
    InterruptEvent,
    InterruptResponse,
} from "@/lib/types";
import { AskUserInput } from "@/components/hitl/ask-user-input";
import type { TimestampedEvent } from "@/lib/stores/agent-progress-store";
import {
    createStreamingContext,
    fileAttachmentToExternalEntry,
} from "@/lib/utils/streaming-helpers";
import { ChatInputBar } from "./chat-input-bar";
import {
    createStreamHandlers,
    readSSEStream,
    buildSavedMessageMetadata,
} from "./use-stream-handler";

const SCENARIO_KEYS: ResearchScenario[] = ["academic", "market", "technical", "news"];

interface MessageListProps {
    messages: Message[];
    streamingContent: string;
    isLoading: boolean;
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
                        streamingEvents={streamingEvents}
                        streamingSources={streamingSources}
                        agentType={streamingAgentType}
                    />
                </div>
            )}
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
    const { provider: selectedProvider, tier, setTier, memoryEnabled } = useSettingsStore();
    const tSettings = useTranslations("settings");
    const t = useTranslations("home");
    const tResearch = useTranslations("research");
    const tChat = useTranslations("chat");
    const tTools = useTranslations("chat.agent.tools");
    const tSkills = useTranslations("skills");

    const getTranslatedToolName = useCallback((toolName: string): string => {
        const toolKey = toolName.toLowerCase();
        try {
            if (typeof tTools.has === "function" && tTools.has(toolKey as Parameters<typeof tTools.has>[0])) {
                return tTools(toolKey as Parameters<typeof tTools>[0]);
            }
        } catch {
            // fall through
        }
        return tTools("default");
    }, [tTools]);
    const [input, setInput] = useState("");
    const [selectedAgent, setSelectedAgent] = useState<AgentType | null>(null);
    const [selectedScenario, setSelectedScenario] = useState<ResearchScenario | null>(null);
    const [selectedDepth, setSelectedDepth] = useState<ResearchDepth>("fast");
    const [selectedSkill, setSelectedSkill] = useState<string | null>(null);
    const [showModelMenu, setShowModelMenu] = useState(false);
    const modelMenuRef = useRef<HTMLDivElement>(null);
    const [streamingContent, setStreamingContent] = useState("");
    const [streamingEvents, setStreamingEvents] = useState<TimestampedEvent[]>([]);
    const [streamingSources, setStreamingSources] = useState<Source[]>([]);
    const [streamingAgentType, setStreamingAgentType] = useState<string | undefined>(undefined);
    const [activeInterrupt, setActiveInterrupt] = useState<InterruptEvent | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);
    const streamingContentRef = useRef("");
    const updateScheduledRef = useRef(false);
    const streamingStartTimeRef = useRef<Date>(new Date());
    const abortControllerRef = useRef<AbortController | null>(null);

    const {
        attachments,
        isUploading,
        addFiles,
        removeAttachment,
        clearAttachments,
        getUploadedFileIds,
    } = useFileUpload({ maxFiles: 10 });

    const { openPicker: openGoogleDrivePicker, error: googleDriveError } = useGoogleDrivePicker({
        onFilesSelected: (driveFiles) => {
            alert(tChat("googleDriveSoon", { count: driveFiles.length }));
        },
        multiSelect: true,
    });

    const handleSourceSelect = (sourceId: string) => {
        if (sourceId === "google-drive") {
            openGoogleDrivePicker();
        }
    };

    const tokenBatchRef = useRef<string[]>([]);
    const batchTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const BATCH_INTERVAL_MS = 50;

    const updateStreamingContent = useCallback((content: string) => {
        if (streamingContentRef.current === content) return;
        streamingContentRef.current = content;

        if (updateScheduledRef.current) return;

        updateScheduledRef.current = true;
        requestAnimationFrame(() => {
            updateScheduledRef.current = false;
            const currentContent = streamingContentRef.current;
            setStreamingContent(prev => {
                if (prev === currentContent) return prev;
                return currentContent;
            });
        });
    }, []);

    const appendTokenBatch = useCallback((token: string) => {
        tokenBatchRef.current.push(token);

        if (!batchTimeoutRef.current) {
            batchTimeoutRef.current = setTimeout(() => {
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

    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (modelMenuRef.current && !modelMenuRef.current.contains(event.target as Node)) {
                setShowModelMenu(false);
            }
        };
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

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

    const activeProgress = useAgentProgressStore((state) => state.activeProgress);
    const {
        startProgress: startAgentProgress,
        addEvent: addAgentEvent,
        updateStage: updateAgentStage,
        endProgress: endAgentProgress,
        clearProgress: clearAgentProgress,
    } = useAgentProgressStore.getState();

    const {
        reset: resetExecutionProgress,
        setStreaming: setExecutionStreaming,
        addEvent: addExecutionEvent,
    } = useExecutionProgressStore.getState();

    const {
        addTerminalLine,
        setCurrentCommand,
        setMode: setComputerMode,
        smartOpen: smartOpenComputer,
        resetUserSelectedMode: resetComputerUserSelectedMode,
        setWorkspaceContext,
        handleWorkspaceUpdate,
        refreshFiles,
        openWorkspacePanel,
        setActiveConversation: setComputerActiveConversation,
        getWorkspaceSandboxId,
    } = useComputerStore.getState();

    const addExternalFile = useComputerStore((state) => state.addExternalFile);
    const openFileInBrowser = useComputerStore((state) => state.openFileInBrowser);

    const workspaceSandboxId = useComputerStore((state) => {
        const id = state.activeConversationId;
        return id ? state.conversationStates[id]?.workspaceSandboxId ?? null : null;
    });

    useEffect(() => {
        setComputerActiveConversation(activeConversationId);
    }, [activeConversationId, setComputerActiveConversation]);

    const activeConversation = hasHydrated ? getActiveConversation() : undefined;
    const messages = activeConversation?.messages || [];

    const loadedConversationsRef = useRef<Set<string>>(new Set());

    useEffect(() => {
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

            if (conversation && conversation.messages.length === 0) {
                if (sessionStatus === "authenticated") {
                    loadedConversationsRef.current.add(activeConversationId);
                    loadConversation(activeConversationId).catch((error) => {
                        console.error("[UnifiedInterface] Failed to load conversation:", error);
                        loadedConversationsRef.current.delete(activeConversationId);
                    });
                }
            } else if (conversation) {
                loadedConversationsRef.current.add(activeConversationId);
            }
        }
    }, [activeConversationId, hasHydrated, getActiveConversation, loadConversation, sessionStatus]);

    useEffect(() => {
        if (!hasHydrated) return;
        if (!activeProgress) return;

        const progressBelongsToDifferentConversation =
            activeProgress.conversationId !== null &&
            activeProgress.conversationId !== activeConversationId;

        const navigatedAwayFromConversations =
            !activeConversationId && activeProgress.conversationId !== null;

        if (progressBelongsToDifferentConversation || navigatedAwayFromConversations) {
            if (!activeProgress.isStreaming) {
                clearAgentProgress();
            }
        }
    }, [activeConversationId, hasHydrated, activeProgress, clearAgentProgress]);

    useEffect(() => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
        }
        flushTokenBatch();
        setStreamingContent("");
        streamingContentRef.current = "";
        setStreamingEvents([]);
        setStreamingSources([]);
        setStreamingAgentType(undefined);
        setActiveInterrupt(null);
        setLoading(false);
        setStreaming(false);
        endAgentProgress();
        setExecutionStreaming(false);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [activeConversationId]);

    const scrollToBottomRef = useRef<number | null>(null);
    const scrollToBottom = useCallback(() => {
        if (scrollToBottomRef.current) return;
        scrollToBottomRef.current = requestAnimationFrame(() => {
            scrollToBottomRef.current = null;
            messagesEndRef.current?.scrollIntoView({ behavior: "auto" });
        });
    }, []);

    useEffect(() => {
        scrollToBottom();
    }, [messages, scrollToBottom]);

    const lastScrollTimeRef = useRef<number>(0);
    useEffect(() => {
        if (!streamingContent) return;
        const now = Date.now();
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
        flushTokenBatch();
        const partialContent = streamingContentRef.current;
        setStreamingContent("");
        streamingContentRef.current = "";
        setStreamingEvents([]);
        setStreamingSources([]);
        setActiveInterrupt(null);
        setLoading(false);
        setStreaming(false);
        endAgentProgress();
        setExecutionStreaming(false);

        if (activeConversationId) {
            const cancelledMessage = partialContent
                ? `${partialContent}\n\n---\n\n*${tChat("requestCancelled")}*`
                : `*${tChat("requestCancelled")}*`;
            await addMessage(activeConversationId, {
                role: "assistant",
                content: cancelledMessage,
            });
        }
    }, [flushTokenBatch, setLoading, setStreaming, endAgentProgress, setExecutionStreaming, activeConversationId, addMessage, tChat]);

    const runStream = async (
        conversationId: string,
        requestBody: Record<string, unknown>,
        agentType: AgentType,
    ) => {
        setLoading(true);
        setStreaming(true);
        streamingStartTimeRef.current = new Date();

        startAgentProgress(conversationId, agentType);
        resetExecutionProgress();
        setExecutionStreaming(true);
        resetComputerUserSelectedMode();

        const hasOpenedTerminalRef = { current: false };

        const thinkingEvent: AgentEvent = {
            type: "stage",
            name: "thinking",
            description: tChat("agent.thinking"),
            status: "running",
        };
        addAgentEvent(thinkingEvent);

        const ctx = createStreamingContext(thinkingEvent);

        const streamHandlers = createStreamHandlers({
            ctx,
            updateStreamingContent,
            flushTokenBatch,
            updateAgentStage,
            addAgentEvent,
            addExecutionEvent,
            setStreamingEvents,
            setStreamingSources,
            setActiveInterrupt,
            setCurrentCommand,
            addTerminalLine,
            smartOpenComputer,
            setWorkspaceContext,
            handleWorkspaceUpdate,
            refreshFiles,
            openFileInBrowser,
            workspaceSandboxId,
            conversationId,
            hasOpenedTerminalRef,
            tChat,
            tSkills,
            getTranslatedToolName,
        });

        try {
            abortControllerRef.current = new AbortController();

            const response = await fetch("/api/v1/query/stream", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: 'include',
                signal: abortControllerRef.current.signal,
                body: JSON.stringify(requestBody),
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);

            const reader = response.body?.getReader();
            if (!reader) throw new Error("No response body");

            await readSSEStream(reader, streamHandlers);

            if (ctx.fullContent || ctx.collectedImages.length > 0) {
                flushTokenBatch();
                setStreamingContent("");
                streamingContentRef.current = "";
                setStreamingEvents([]);
                setStreamingSources([]);
                setLoading(false);

                const metadata = buildSavedMessageMetadata(ctx);
                await addMessage(conversationId, {
                    role: "assistant",
                    content: ctx.fullContent,
                    metadata,
                });
            }
        } catch (error) {
            if (error instanceof Error && error.name === 'AbortError') {
                // Request cancelled by user
            } else {
                console.error("Stream error:", error);
                await addMessage(conversationId, { role: "assistant", content: tChat("connectionError") });
            }
        } finally {
            abortControllerRef.current = null;
            flushTokenBatch();
            setStreamingContent("");
            streamingContentRef.current = "";
            setStreamingEvents([]);
            setStreamingSources([]);
            setLoading(false);
            setStreaming(false);
            endAgentProgress();
            setExecutionStreaming(false);
        }
    };

    const handleSubmit = async () => {
        if (!input.trim() || isLoading || isUploading) return;

        const userMessage = input.trim();
        const attachmentIds = getUploadedFileIds();
        const messageAttachments = attachments.filter(a => a.status === 'uploaded');
        for (const att of messageAttachments) {
            addExternalFile(fileAttachmentToExternalEntry(att, "upload"));
        }
        const skillToUse = selectedSkill;
        setInput("");
        clearAttachments();

        if (selectedAgent === "research" && selectedScenario) {
            await handleAgentTask(userMessage, "research", attachmentIds, messageAttachments);
            setSelectedAgent(null);
            setSelectedScenario(null);
        } else if (selectedAgent === "data" || selectedAgent === "app" || selectedAgent === "image" || selectedAgent === "slide") {
            await handleAgentTask(userMessage, selectedAgent, attachmentIds, messageAttachments);
            setSelectedAgent(null);
        } else if (!selectedAgent && activeConversation?.type === "research") {
            await handleAgentTask(userMessage, "research", attachmentIds, messageAttachments);
        } else if (!selectedAgent && activeConversation?.type === "data") {
            await handleAgentTask(userMessage, activeConversation.type as AgentType, attachmentIds, messageAttachments);
        } else if (!selectedAgent && activeConversation?.type === "app") {
            await handleAgentTask(userMessage, activeConversation.type as AgentType, attachmentIds, messageAttachments);
        } else if (!selectedAgent && activeConversation?.type === "image") {
            await handleAgentTask(userMessage, activeConversation.type as AgentType, attachmentIds, messageAttachments);
        } else if (!selectedAgent && activeConversation?.type === "slide") {
            await handleAgentTask(userMessage, activeConversation.type as AgentType, attachmentIds, messageAttachments);
        } else {
            await handleChat(userMessage, false, attachmentIds, messageAttachments, skillToUse);
        }
    };

    const handleChat = async (
        userMessage: string,
        skipUserMessage = false,
        attachmentIds: string[] = [],
        messageAttachments: FileAttachment[] = [],
        explicitSkill: string | null = null
    ) => {
        setStreamingContent("");
        streamingContentRef.current = "";
        tokenBatchRef.current = [];
        setStreamingEvents([]);
        setStreamingSources([]);
        setStreamingAgentType("task");

        let conversationId = activeConversationId;
        if (!conversationId || activeConversation?.type !== "task") {
            conversationId = await createConversation("task");
        }

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

        const historyAttachmentIds = getConversationAttachmentIds(conversationMessages);
        const combinedAttachmentIds = Array.from(new Set([...historyAttachmentIds, ...attachmentIds]));

        if (!skipUserMessage) {
            await addMessage(conversationId, {
                role: "user",
                content: userMessage,
                attachments: messageAttachments,
                ...(explicitSkill && { metadata: { skill: explicitSkill } }),
            });
        }

        await runStream(conversationId, {
            message: userMessage,
            mode: "task",
            ...(selectedProvider !== "auto" && { provider: selectedProvider }),
            tier,
            memory_enabled: memoryEnabled,
            ...((explicitSkill || selectedSkill) && { skills: [explicitSkill || selectedSkill] }),
            attachment_ids: combinedAttachmentIds,
            conversation_id: conversationId,
            history,
            locale,
        }, "task");
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
        setStreamingEvents([]);
        setStreamingSources([]);
        setStreamingAgentType(agentType);

        const conversationType = agentType === "research" ? "research" : agentType;

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

        const historyAttachmentIds = getConversationAttachmentIds(conversationMessages);
        const combinedAttachmentIds = agentType === "research"
            ? attachmentIds
            : Array.from(new Set([...historyAttachmentIds, ...attachmentIds]));

        await addMessage(conversationId, {
            role: "user",
            content: userMessage,
            attachments: messageAttachments
        });

        await runStream(conversationId, {
            message: userMessage,
            mode: agentType,
            ...(selectedProvider !== "auto" && { provider: selectedProvider }),
            tier,
            memory_enabled: memoryEnabled,
            ...(selectedSkill && { skills: [selectedSkill] }),
            ...(agentType === "research" && selectedScenario && { scenario: selectedScenario }),
            ...(agentType === "research" && { depth: selectedDepth }),
            attachment_ids: combinedAttachmentIds,
            conversation_id: conversationId,
            history,
            locale,
        }, agentType);
    };

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

        const conversationType = activeConversation?.type;
        if (conversationType === "research" || conversationType === "data" || conversationType === "image" || conversationType === "app" || conversationType === "slide") {
            await handleAgentTask(userMessage, conversationType as AgentType, attachmentIds, userMessageAttachments);
        } else {
            await handleChat(userMessage, true, attachmentIds, userMessageAttachments);
        }
    };

    const handleRegenerate = useCallback((messageId: string) => {
        handleRegenerateRef.current?.(messageId);
    }, []);

    const handleInterruptResponse = useCallback(async (response: InterruptResponse) => {
        if (!activeInterrupt) {
            console.warn("[HITL] No active interrupt to respond to");
            return;
        }

        const respondingToInterruptId = response.interrupt_id;

        try {
            const threadId = activeConversationId || "default";

            const res = await fetch(`/api/v1/hitl/respond/${threadId}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
                body: JSON.stringify(response),
            });

            const result = await res.json();

            if (!res.ok) {
                console.error("[HITL] Server error:", result);
            }
        } catch (error) {
            console.error("[HITL] Failed to submit response:", error);
        } finally {
            setActiveInterrupt((current) => {
                if (current?.interrupt_id === respondingToInterruptId) {
                    return null;
                }
                return current;
            });
        }
    }, [activeInterrupt, activeConversationId]);

    const handleInterruptCancel = useCallback(() => {
        if (!activeInterrupt) return;

        handleInterruptResponse({
            interrupt_id: activeInterrupt.interrupt_id,
            action: "cancel",
        });
    }, [activeInterrupt, handleInterruptResponse]);

    const isProcessing = isLoading;
    const hasMessages = messages.length > 0 || streamingContent || isLoading;

    const allUsageEvents = useMemo(() => {
        const events: AgentEvent[] = [];
        for (const msg of messages) {
            if (msg.role === "assistant" && msg.metadata?.agentEvents) {
                for (const ev of msg.metadata.agentEvents) {
                    if (ev.type === "usage") {
                        events.push(ev);
                    }
                }
            }
        }
        return events;
    }, [messages]);

    const getPlaceholder = () => {
        if (selectedAgent === "research" && selectedScenario) {
            return t("researchPlaceholder", { scenario: tResearch(`${selectedScenario}.name`) });
        }
        if (selectedAgent === "data") return t("dataPlaceholder");
        if (selectedAgent === "app") return t("appPlaceholder");
        if (selectedAgent === "image") return t("imagePlaceholder");
        if (selectedAgent === "slide") return t("slidePlaceholder");
        return t("inputPlaceholder");
    };

    const handleTierChange = useCallback((newTier: "max" | "pro" | "lite") => {
        setTier(newTier);
        setShowModelMenu(false);
    }, [setTier]);

    const handleToggleModelMenu = useCallback(() => {
        setShowModelMenu(prev => !prev);
    }, []);

    return (
        <div className="flex-1 flex flex-col overflow-hidden">
            {hasMessages && (
                <div className="flex-1 overflow-y-auto">
                    <div className="max-w-4xl mx-auto px-4 md:px-6 py-4 md:py-6">
                        <MessageList
                            messages={messages}
                            streamingContent={streamingContent}
                            isLoading={isLoading}
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

            <ChatInputBar
                hasMessages={!!hasMessages}
                input={input}
                onInputChange={setInput}
                onSubmit={handleSubmit}
                onStop={handleStop}
                isProcessing={isProcessing}
                isUploading={isUploading}
                inputRef={inputRef}
                placeholder={getPlaceholder()}
                attachments={attachments}
                onRemoveAttachment={removeAttachment}
                onFilesSelected={addFiles}
                onSourceSelect={handleSourceSelect}
                tier={tier}
                onTierChange={handleTierChange}
                showModelMenu={showModelMenu}
                onToggleModelMenu={handleToggleModelMenu}
                modelMenuRef={modelMenuRef}
                selectedSkill={selectedSkill}
                onSkillChange={setSelectedSkill}
                allUsageEvents={allUsageEvents}
                welcomeTitle={t("welcomeTitle")}
                welcomeSubtitle={t("welcomeSubtitle")}
                tSettings={tSettings}
                tChat={tChat}
            />

        </div>
    );
}
