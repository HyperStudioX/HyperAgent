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
import { FileUploadButton } from "@/components/chat/file-upload-button";
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

export function UnifiedInterface() {
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
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);
    const researchRef = useRef<HTMLDivElement>(null);
    const streamingContentRef = useRef("");
    const updateScheduledRef = useRef(false);
    const detectedSearchQueriesRef = useRef<Set<string>>(new Set());
    const searchStageCompletedRef = useRef(false);

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
            console.log("Google Drive files selected:", driveFiles);
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
        streamingContentRef.current = content;
        if (!updateScheduledRef.current) {
            updateScheduledRef.current = true;
            // Use requestAnimationFrame for smooth updates
            requestAnimationFrame(() => {
                setStreamingContent(streamingContentRef.current);
                updateScheduledRef.current = false;
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

    const stripAssistantSearchTags = useCallback((content: string) => {
        return content
            .replace(/<search_quality_score>[\s\S]*?<\/search_quality_score>/gi, "")
            .replace(/<search_query>[\s\S]*?<\/search_query>/gi, "")
            .replace(/<search>[\s\S]*?<\/search>/gi, "");
    }, []);

    const extractSearchQueries = useCallback((content: string) => {
        const matches = content.matchAll(/<search>([\s\S]*?)<\/search>/gi);
        const queries: string[] = [];
        for (const match of matches) {
            const query = (match[1] || "").trim();
            if (query) {
                queries.push(query);
            }
        }
        return queries;
    }, []);

    const markSearchStageCompleted = useCallback(() => {
        if (searchStageCompletedRef.current) {
            return null;
        }
        searchStageCompletedRef.current = true;
        return {
            type: "stage",
            data: {
                name: "tool",
                description: "Search completed",
                status: "completed",
            },
        };
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

    const scrollToBottom = () => {
        // Use 'auto' instead of 'smooth' to avoid layout/update loops during frequent updates
        messagesEndRef.current?.scrollIntoView({ behavior: "auto" });
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
        setStreamingEvents([]);
        detectedSearchQueriesRef.current = new Set();
        searchStageCompletedRef.current = true;

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

        let fullContent = "";
        const collectedEvents: any[] = [];

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

                            // Debug logging
                            if (process.env.NODE_ENV === "development") {
                                console.log("[SSE Event]", event.type, event);
                            }

                            if (event.type === "token" && event.data) {
                                fullContent += event.data;
                                // Add token to streaming events for stage progress
                                collectedEvents.push(event);
                                const searchQueries = extractSearchQueries(fullContent);
                                for (const query of searchQueries) {
                                    if (detectedSearchQueriesRef.current.has(query)) {
                                        continue;
                                    }
                                    detectedSearchQueriesRef.current.add(query);
                                    const searchEvent = {
                                        type: "tool_call",
                                        data: { tool: "web_search", args: { query } },
                                    };
                                    collectedEvents.push(searchEvent);
                                    setStreamingEvents(prev => [...prev, searchEvent]);
                                }
                                if (detectedSearchQueriesRef.current.size > 0 && !searchStageCompletedRef.current) {
                                    continue;
                                }
                                // Use batched token updates for smoother rendering
                                const sanitized = stripAssistantSearchTags(fullContent);
                                streamingContentRef.current = sanitized;
                                appendTokenBatch("");
                                setAgentStatus(null);
                            } else if (event.type === "stage") {
                                // Flush tokens before stage change for immediate visual feedback
                                flushTokenBatch();
                                // Handle both flat structure and nested data structure
                                const stageName = event.name || event.data?.name;
                                const stageStatus = event.status || event.data?.status;
                                const stageDescription = event.description || event.data?.description;
                                if (
                                    stageName === "tool" &&
                                    stageStatus === "completed" &&
                                    !searchStageCompletedRef.current
                                ) {
                                    searchStageCompletedRef.current = true;
                                    const sanitized = stripAssistantSearchTags(fullContent);
                                    if (sanitized.trim().length > 0) {
                                        updateStreamingContent(sanitized);
                                    }
                                }
                                setAgentStatus(stageDescription);
                                collectedEvents.push(event);
                                setStreamingEvents(prev => [...prev.filter(e => e.type !== 'stage' || (e.status || e.data?.status) !== 'pending'), event]);
                            } else if (event.type === "tool_call" && event.data) {
                                const toolName = event.data.tool || "web";
                                if (toolName === "web_search" || toolName === "google_search" || toolName === "web") {
                                    setAgentStatus(tChat("agent.searching", { query: event.data.args?.query || "web" }));
                                } else {
                                    setAgentStatus(tChat("agent.executing", { tool: toolName }));
                                }
                                collectedEvents.push(event);
                                setStreamingEvents(prev => [...prev, event]);
                            } else if (event.type === "tool_result" && event.data) {
                                if (!searchStageCompletedRef.current) {
                                    searchStageCompletedRef.current = true;
                                    const sanitized = stripAssistantSearchTags(fullContent);
                                    if (sanitized.trim().length > 0) {
                                        updateStreamingContent(sanitized);
                                    }
                                }
                                collectedEvents.push(event);
                                setStreamingEvents(prev => [...prev, event]);
                            } else if (event.type === "error") {
                                fullContent = tChat("agent.error", { error: event.data });
                                updateStreamingContent(fullContent);
                                if (detectedSearchQueriesRef.current.size > 0 && !searchStageCompletedRef.current) {
                                    searchStageCompletedRef.current = true;
                                    const failedEvent = {
                                        type: "stage",
                                        data: {
                                            name: "tool",
                                            description: "Search failed",
                                            status: "failed",
                                        },
                                    };
                                    collectedEvents.push(failedEvent);
                                    setStreamingEvents(prev => [...prev, failedEvent]);
                                }
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
                const sanitizedContent = stripAssistantSearchTags(fullContent);
                await addMessage(conversationId, {
                    role: "assistant",
                    content: sanitizedContent,
                    metadata: collectedEvents.length ? { agentEvents: collectedEvents } : undefined,
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
            setStreamingEvents([]);
            setLoading(false);
            setStreaming(false);
            searchStageCompletedRef.current = true;
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
        setStreamingEvents([]);
        detectedSearchQueriesRef.current = new Set();
        searchStageCompletedRef.current = true;

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

        // Set initial status to give immediate feedback
        if (agentType === "data") {
            setAgentStatus(tChat("agent.analyzing") || "Starting analysis...");
        } else if (agentType === "research") {
            setAgentStatus(tChat("agent.researching") || "Starting research...");
        } else {
            setAgentStatus(tChat("agent.processing"));
        }

        let fullContent = "";
        const collectedEvents: any[] = [];

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

                            // Debug logging
                            if (process.env.NODE_ENV === "development") {
                                console.log("[SSE Event]", event.type, event);
                            }

                            if (event.type === "token" && event.data) {
                                fullContent += event.data;
                                // Add token to streaming events for stage progress
                                collectedEvents.push(event);
                                const searchQueries = extractSearchQueries(fullContent);
                                for (const query of searchQueries) {
                                    if (detectedSearchQueriesRef.current.has(query)) {
                                        continue;
                                    }
                                    detectedSearchQueriesRef.current.add(query);
                                    const searchEvent = {
                                        type: "tool_call",
                                        data: { tool: "web_search", args: { query } },
                                    };
                                    collectedEvents.push(searchEvent);
                                    setStreamingEvents(prev => [...prev, searchEvent]);
                                }
                                if (detectedSearchQueriesRef.current.size > 0 && !searchStageCompletedRef.current) {
                                    continue;
                                }
                                // Use batched token updates for smoother rendering
                                const sanitized = stripAssistantSearchTags(fullContent);
                                streamingContentRef.current = sanitized;
                                appendTokenBatch("");
                                setAgentStatus(null);
                            } else if (event.type === "stage") {
                                // Flush tokens before stage change for immediate visual feedback
                                flushTokenBatch();
                                // Handle both flat structure and nested data structure
                                const stageName = event.name || event.data?.name;
                                const stageStatus = event.status || event.data?.status;
                                const stageDescription = event.description || event.data?.description;
                                if (
                                    stageName === "tool" &&
                                    stageStatus === "completed" &&
                                    !searchStageCompletedRef.current
                                ) {
                                    searchStageCompletedRef.current = true;
                                    const sanitized = stripAssistantSearchTags(fullContent);
                                    if (sanitized.trim().length > 0) {
                                        updateStreamingContent(sanitized);
                                    }
                                }
                                setAgentStatus(stageDescription);
                                collectedEvents.push(event);
                                setStreamingEvents(prev => [...prev.filter(e => e.type !== 'stage' || (e.status || e.data?.status) !== 'pending'), event]);
                            } else if (event.type === "tool_call" && event.data) {
                                const toolName = event.data.tool || "tool";
                                setAgentStatus(tChat("agent.executing", { tool: toolName }));
                                collectedEvents.push(event);
                                setStreamingEvents(prev => [...prev, event]);
                            } else if (event.type === "tool_result" && event.data) {
                                if (!searchStageCompletedRef.current) {
                                    searchStageCompletedRef.current = true;
                                    const sanitized = stripAssistantSearchTags(fullContent);
                                    if (sanitized.trim().length > 0) {
                                        updateStreamingContent(sanitized);
                                    }
                                }
                                collectedEvents.push(event);
                                setStreamingEvents(prev => [...prev, event]);
                            } else if (event.type === "error") {
                                fullContent = tChat("agent.error", { error: event.data });
                                updateStreamingContent(fullContent);
                                if (detectedSearchQueriesRef.current.size > 0 && !searchStageCompletedRef.current) {
                                    searchStageCompletedRef.current = true;
                                    const failedEvent = {
                                        type: "stage",
                                        data: {
                                            name: "tool",
                                            description: "Search failed",
                                            status: "failed",
                                        },
                                    };
                                    collectedEvents.push(failedEvent);
                                    setStreamingEvents(prev => [...prev, failedEvent]);
                                }
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
                const sanitizedContent = stripAssistantSearchTags(fullContent);
                await addMessage(conversationId, {
                    role: "assistant",
                    content: sanitizedContent,
                    metadata: collectedEvents.length ? { agentEvents: collectedEvents } : undefined,
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
            setStreamingEvents([]);
            setLoading(false);
            setStreaming(false);
            searchStageCompletedRef.current = true;
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
                            {(streamingContent || isLoading) && (
                                <div className="animate-fade-in">
                                    <MessageBubble
                                        message={{
                                            id: "streaming",
                                            role: "assistant",
                                            content: streamingContent || "",
                                            createdAt: new Date(),
                                        }}
                                        isStreaming={true}
                                        status={agentStatus}
                                        agentEvents={streamingEvents}
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
                                className="flex items-center justify-center gap-4 mb-8 animate-slide-up"
                                style={{ animationDelay: '0.1s', animationFillMode: 'backwards' }}
                            >
                                <div className="relative w-14 h-14 flex items-center justify-center">
                                    <div className="absolute inset-0 bg-gradient-to-br from-foreground/5 to-foreground/[0.02] rounded-2xl blur-xl" />
                                    <Image
                                        src="/images/logo-dark.svg"
                                        alt="HyperAgent"
                                        width={56}
                                        height={56}
                                        priority
                                        className="dark:hidden relative z-10 transition-all duration-300 hover:scale-105"
                                        style={{ opacity: 0.9 }}
                                    />
                                    <Image
                                        src="/images/logo-light.svg"
                                        alt="HyperAgent"
                                        width={56}
                                        height={56}
                                        priority
                                        className="hidden dark:block relative z-10 transition-all duration-300 hover:scale-105"
                                        style={{ opacity: 0.92 }}
                                    />
                                </div>
                                <h1 className="text-[40px] md:text-5xl font-semibold text-foreground tracking-[-0.02em] opacity-95">
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
                            "relative flex flex-col bg-card rounded-lg border border-border focus-within:border-foreground/30 transition-colors"
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
                                        "flex-1 bg-transparent text-foreground placeholder:text-muted-foreground focus:outline-none resize-none leading-relaxed",
                                        hasMessages
                                            ? "min-h-[64px] max-h-[160px] py-3 px-4 text-base"
                                            : "min-h-[100px] md:min-h-[110px] max-h-[200px] py-4 px-5 text-base"
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

                            {/* Bottom bar with plus button, hint and send button */}
                            <div className="flex items-center justify-between px-2 md:px-3 py-2 border-t border-border/50">
                                <div className="flex items-center gap-1">
                                    <FileUploadButton
                                        onFilesSelected={addFiles}
                                        onSourceSelect={handleSourceSelect}
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
                                        "px-4 py-2 rounded-lg transition-colors min-h-[44px] flex items-center justify-center gap-2 font-medium text-sm",
                                        input.trim() && !isProcessing && !isUploading
                                            ? "bg-primary text-primary-foreground hover:bg-primary/90"
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
                                                    <div className="bg-card border border-border rounded-lg overflow-hidden min-w-[220px]">
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
