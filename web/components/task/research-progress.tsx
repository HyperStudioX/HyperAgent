"use client";

import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useTranslations, useLocale } from "next-intl";
import {
    Loader2,
    GraduationCap,
    TrendingUp,
    Code2,
    Newspaper,
    Share2,
    ArrowLeft,
    AlertCircle,
    Monitor,
    X,
    PanelRightClose,
    PanelRight,
} from "lucide-react";
import { ResearchResultView } from "@/components/query/research-report-view";
import { Button } from "@/components/ui/button";
import { TaskProgressPanel } from "@/components/ui/task-progress-panel";
import { useTaskStore } from "@/lib/stores/task-store";
import { useAgentProgressStore, type ComputerStreamInfo, type TimestampedEvent } from "@/lib/stores/agent-progress-store";
import type { ResearchStep, Source, ResearchScenario, AgentEvent } from "@/lib/types";
import type { ResearchTask } from "@/lib/stores/task-store";

// Status types for type safety
type TaskStatus = ResearchTask["status"];
type StepStatus = ResearchStep["status"];

// Event handler type for dispatch table
type EventHandler = (event: Record<string, unknown>, context: EventHandlerContext) => void;

interface EventHandlerContext {
    taskId: string;
    currentSteps: React.MutableRefObject<ResearchStep[]>;
    currentSources: React.MutableRefObject<Source[]>;
    fullResult: React.MutableRefObject<string>;
    updateTaskStatus: (id: string, status: TaskStatus, error?: string) => void;
    updateTaskSteps: (id: string, steps: ResearchStep[]) => void;
    updateTaskSources: (id: string, sources: Source[]) => void;
    updateTaskResult: (id: string, result: string) => void;
    setResearchResult: (result: string) => void;
    setError: (error: string | null) => void;
    addEvent: (event: AgentEvent) => void;
    setBrowserStream: (stream: ComputerStreamInfo | null) => void;
}

// Event dispatch table for O(1) lookup instead of if/else chain
const createEventHandlers = (): Map<string, EventHandler> => {
    const handlers = new Map<string, EventHandler>();

    handlers.set("task_started", (event, ctx) => {
        const backendTaskId = event.task_id;
        if (backendTaskId) {
            console.log(`[ResearchProgress] Backend task started: ${backendTaskId}`);
        }
        ctx.updateTaskStatus(ctx.taskId, "running");
    });

    handlers.set("stage", (event, ctx) => {
        const stepName = (event.name || (event.data as Record<string, unknown>)?.name) as string;
        const stepStatus = (event.status || (event.data as Record<string, unknown>)?.status) as StepStatus;
        if (stepName && stepStatus) {
            ctx.currentSteps.current = ctx.currentSteps.current.map((s) =>
                s.type === stepName ? { ...s, status: stepStatus } : s
            );
            ctx.updateTaskSteps(ctx.taskId, ctx.currentSteps.current);

            const stepInfo = INITIAL_STEPS.find(s => s.type === stepName);
            ctx.addEvent({
                type: "stage",
                name: stepName,
                description: (event.description || stepInfo?.description || stepName) as string,
                status: stepStatus,
            });
        }
    });

    handlers.set("source", (event, ctx) => {
        const sourceData = (event.data || event) as Record<string, unknown>;
        const newSource: Source = {
            id: (sourceData.id || event.id || `source-${ctx.currentSources.current.length}`) as string,
            title: (sourceData.title || event.title || "Source") as string,
            url: (sourceData.url || event.url || "") as string,
            snippet: (sourceData.snippet || event.snippet) as string | undefined,
        };
        ctx.currentSources.current = [...ctx.currentSources.current, newSource];
        ctx.updateTaskSources(ctx.taskId, ctx.currentSources.current);

        ctx.addEvent({
            type: "source",
            name: newSource.title,
            data: {
                id: newSource.id,
                title: newSource.title,
                url: newSource.url,
                snippet: newSource.snippet,
            },
        } as AgentEvent);
    });

    handlers.set("tool_call", (event, ctx) => {
        ctx.addEvent({
            type: "tool_call",
            tool: (event.tool || "tool") as string,
            args: (event.args || {}) as Record<string, unknown>,
            id: event.id as string,
        } as AgentEvent);
    });

    handlers.set("tool_result", (event, ctx) => {
        ctx.addEvent({
            type: "tool_result",
            tool: event.tool as string,
            id: event.id as string,
            data: event.output || event.data,
        } as AgentEvent);
    });

    handlers.set("routing", (event, ctx) => {
        ctx.addEvent({
            type: "routing",
            name: (event.agent || event.selected_agent) as string,
            data: event,
        } as AgentEvent);
    });

    handlers.set("handoff", (event, ctx) => {
        ctx.addEvent({
            type: "handoff",
            name: event.target as string,
            target: event.target as string,
            data: event,
        } as AgentEvent);
    });

    handlers.set("token", (event, ctx) => {
        const tokenContent = event.data || event.content || "";
        if (tokenContent) {
            ctx.fullResult.current += typeof tokenContent === "string" ? tokenContent : String(tokenContent);
            ctx.setResearchResult(ctx.fullResult.current);
            ctx.updateTaskResult(ctx.taskId, ctx.fullResult.current);
        }
    });

    handlers.set("error", (event, ctx) => {
        const errorMsg = (event.data || event.message || "Unknown error") as string;
        ctx.setError(errorMsg);
        ctx.updateTaskStatus(ctx.taskId, "failed", errorMsg);
        ctx.addEvent({
            type: "error",
            data: errorMsg,
        } as AgentEvent);
    });

    handlers.set("browser_stream", (event, ctx) => {
        const streamUrl = event.stream_url as string;
        const sandboxId = event.sandbox_id as string;
        const authKey = event.auth_key as string | undefined;
        if (streamUrl && sandboxId) {
            ctx.setBrowserStream({
                streamUrl,
                sandboxId,
                authKey,
            });
            ctx.addEvent({
                type: "stage",
                name: "browser",
                description: "Browser session started - live view available",
                status: "running",
            });
        }
    });

    handlers.set("browser_action", (event, ctx) => {
        const action = event.action as string;
        const description = event.description as string;
        const target = event.target as string | undefined;
        const status = (event.status as string) || "running";

        // Add browser action as a stage event for progress display
        ctx.addEvent({
            type: "stage",
            name: `browser_${action}`,
            description: target ? `${description}: ${target}` : description,
            status: status === "completed" ? "completed" : "running",
        });
    });

    return handlers;
};

// Create handlers once at module level
const EVENT_HANDLERS = createEventHandlers();

const SCENARIO_ICONS: Record<ResearchScenario, React.ReactNode> = {
    academic: <GraduationCap className="w-4 h-4" />,
    market: <TrendingUp className="w-4 h-4" />,
    technical: <Code2 className="w-4 h-4" />,
    news: <Newspaper className="w-4 h-4" />,
};

// Define all research steps upfront
const INITIAL_STEPS: ResearchStep[] = [
    { id: "1", type: "thinking", description: "Thinking", status: "pending" },
    { id: "2", type: "search", description: "Searching", status: "pending" },
    { id: "3", type: "analyze", description: "Analyzing", status: "pending" },
    { id: "4", type: "synthesize", description: "Synthesizing", status: "pending" },
    { id: "5", type: "write", description: "Writing", status: "pending" },
];

interface TaskInfo {
    query: string;
    scenario: ResearchScenario;
    depth: string;
}

function ResearchBrowserStreamIframe({ stream }: { stream: ComputerStreamInfo }) {
    const streamUrl = useMemo(() => {
        const base = stream.streamUrl;
        const auth = stream.authKey;
        if (auth && !base.includes("authKey=")) {
            const sep = base.includes("?") ? "&" : "?";
            return `${base}${sep}authKey=${encodeURIComponent(auth)}`;
        }
        return base;
    }, [stream.streamUrl, stream.authKey]);

    return (
        <div className="p-3">
            <div className="rounded-lg overflow-hidden border border-border bg-black">
                <iframe
                    src={streamUrl}
                    className="w-full h-[400px]"
                    allow="autoplay; fullscreen"
                    referrerPolicy="no-referrer"
                />
            </div>
        </div>
    );
}

interface ResearchProgressProps {
    taskId: string;
}

export function ResearchProgress({ taskId }: ResearchProgressProps) {
    const router = useRouter();
    const locale = useLocale();
    const t = useTranslations("task");
    const tResearch = useTranslations("research");
    const tChat = useTranslations("chat");

    // Use selective store subscriptions to avoid unnecessary re-renders
    const hasHydrated = useTaskStore((state) => state.hasHydrated);
    const createTask = useTaskStore((state) => state.createTask);
    const updateTaskStatus = useTaskStore((state) => state.updateTaskStatus);
    const updateTaskSteps = useTaskStore((state) => state.updateTaskSteps);
    const updateTaskSources = useTaskStore((state) => state.updateTaskSources);
    const updateTaskResult = useTaskStore((state) => state.updateTaskResult);
    const setActiveTask = useTaskStore((state) => state.setActiveTask);

    // Get task by ID selector - only re-renders when this specific task changes
    const existingTask = useTaskStore(
        useCallback((state) => state.tasks.find((task) => task.id === taskId), [taskId])
    );

    // Agent progress store for unified progress display (includes browser stream state)
    const {
        startProgress,
        addEvent,
        endProgress,
        activeProgress,
        showBrowserStream,
        setShowBrowserStream,
        setBrowserStream,
    } = useAgentProgressStore();

    // Get browser stream, events, and current action from shared store
    const browserStream = activeProgress?.browserStream ?? null;
    const currentStage = activeProgress?.currentStage ?? null;
    const currentStageDescription = activeProgress?.currentStageDescription ?? null;
    const progressEvents = activeProgress?.events ?? [];
    const progressSources = activeProgress?.sources ?? [];

    // Refs for stable references in callbacks
    const taskLoadedRef = useRef(false);
    const abortControllerRef = useRef<AbortController | null>(null);

    const [taskInfo, setTaskInfo] = useState<TaskInfo | null>(null);
    const [isResearching, setIsResearching] = useState(false);
    const [researchResult, setResearchResult] = useState<string | unknown[]>("");
    const [error, setError] = useState<string | null>(null);
    const [hasStarted, setHasStarted] = useState(false);
    const [isExistingTask, setIsExistingTask] = useState(false);

    // Load task from store or API - optimized with reduced dependencies
    useEffect(() => {
        // Prevent duplicate loads
        if (taskLoadedRef.current) return;

        const fetchTask = async () => {
            // 1. Check localStorage for NEW task first (just submitted from Home)
            const storedTaskInfo = localStorage.getItem(`task-${taskId}`);
            if (storedTaskInfo) {
                console.log(`[ResearchProgress] New task detected in local storage for ${taskId}`);
                try {
                    const info = JSON.parse(storedTaskInfo) as TaskInfo;
                    setTaskInfo(info);
                    taskLoadedRef.current = true;

                    // Also initialize in task store if hydrated
                    if (hasHydrated) {
                        createTask(taskId, info.query, info.scenario, info.depth);
                        setActiveTask(taskId);
                    }
                    return; // Successfully initialized new task, skip API fetch
                } catch (e) {
                    console.error("[ResearchProgress] Failed to parse stored task info:", e);
                    localStorage.removeItem(`task-${taskId}`);
                }
            }

            // 2. Fallback to Task Store if hydrated - use the selector result
            if (hasHydrated && existingTask) {
                // If task has no result and is completed, try to fetch from API
                if (!existingTask.result && existingTask.status === "completed") {
                    // Fall through to API fetch
                } else {
                    setTaskInfo({
                        query: existingTask.query,
                        scenario: existingTask.scenario,
                        depth: existingTask.depth,
                    });
                    setResearchResult(existingTask.result);
                    setError(existingTask.error || null);
                    setIsExistingTask(true);
                    setActiveTask(taskId);
                    taskLoadedRef.current = true;

                    if (existingTask.status !== "running" && existingTask.status !== "pending") {
                        setHasStarted(true);
                        setIsResearching(false);
                    }
                    return;
                }
            }

            // 3. Otherwise fetch from API (existing task from history)
            if (!hasHydrated) return; // Wait for hydration before API fetch

            console.log(`[ResearchProgress] Fetching task ${taskId} from API...`);
            try {
                const response = await fetch(`/api/v1/tasks/${taskId}/result`, {
                    credentials: 'include',
                });
                if (response.ok) {
                    const data = await response.json();
                    console.log(`[ResearchProgress] Task data received from API:`, data);
                    taskLoadedRef.current = true;

                    setTaskInfo({
                        query: data.query,
                        scenario: data.scenario,
                        depth: data.depth,
                    });

                    // Map steps and sources from backend format to frontend format
                    if (data.steps) {
                        interface StepData { id: string; type: string; description: string; status: string; }
                        const mappedSteps = (data.steps as StepData[]).map((s) => ({
                            id: s.id,
                            type: s.type,
                            description: s.description,
                            status: s.status,
                        }));
                        // Deduplicate steps using Map for O(1) lookup
                        const stepMap = new Map<string, StepData>();
                        mappedSteps.forEach(step => stepMap.set(step.type, step));
                        updateTaskSteps(taskId, Array.from(stepMap.values()) as ResearchStep[]);
                    }

                    if (data.sources) {
                        interface SourceData { id: string; title: string; url: string; snippet?: string; }
                        const mappedSources = (data.sources as SourceData[]).map((s) => ({
                            id: s.id,
                            title: s.title,
                            url: s.url,
                            snippet: s.snippet,
                        }));
                        updateTaskSources(taskId, mappedSources);
                    }

                    if (data.report) {
                        setResearchResult(data.report);
                        updateTaskResult(taskId, data.report);
                    }

                    setError(data.error || null);
                    setIsExistingTask(true);
                    setActiveTask(taskId);

                    if (data.status === "completed" || data.status === "failed") {
                        setHasStarted(true);
                        setIsResearching(false);
                    }
                    return;
                } else if (response.status === 404) {
                    setError(t("taskNotFoundMessage"));
                } else if (response.status === 401) {
                    console.warn(`[ResearchProgress] Authentication required - please log in`);
                    setError("Please log in to view this research task");
                } else if (response.status === 403) {
                    console.warn(`[ResearchProgress] Access denied to task`);
                    setError("You don't have permission to view this task");
                } else {
                    const errorData = await response.json().catch(() => ({}));
                    console.warn(`[ResearchProgress] API returned status ${response.status}:`, errorData);
                    setError(errorData.detail || "Failed to load task details");
                }
            } catch (err) {
                console.error("[ResearchProgress] API fetch failed:", err);
                setError("Connection error while loading task");
            }
        };

        fetchTask();
    }, [taskId, hasHydrated, existingTask, createTask, setActiveTask, updateTaskSteps, updateTaskSources, updateTaskResult, t]);

    // Refs for streaming state - avoids recreating arrays on each event
    const currentStepsRef = useRef<ResearchStep[]>([...INITIAL_STEPS]);
    const currentSourcesRef = useRef<Source[]>([]);
    const fullResultRef = useRef<string>("");

    // Memoize startResearch with minimal dependencies using refs
    const startResearch = useCallback(async (info: TaskInfo) => {
        // Abort any existing request
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
        abortControllerRef.current = new AbortController();

        setIsResearching(true);
        setResearchResult("");
        setError(null);

        // Reset refs
        currentStepsRef.current = [...INITIAL_STEPS];
        currentSourcesRef.current = [];
        fullResultRef.current = "";

        // Initialize steps in task store
        updateTaskSteps(taskId, [...INITIAL_STEPS]);
        updateTaskStatus(taskId, "running");

        // Start agent progress tracking
        startProgress(taskId, "research");

        // Create event handler context
        const context: EventHandlerContext = {
            taskId,
            currentSteps: currentStepsRef,
            currentSources: currentSourcesRef,
            fullResult: fullResultRef,
            updateTaskStatus,
            updateTaskSteps,
            updateTaskSources,
            updateTaskResult,
            setResearchResult,
            setError,
            addEvent,
            setBrowserStream,
        };

        try {
            const response = await fetch("/api/v1/query/stream", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: 'include',
                body: JSON.stringify({
                    message: info.query,
                    mode: "research",
                    scenario: info.scenario,
                    depth: info.depth,
                    task_id: taskId,
                    locale: locale,
                }),
                signal: abortControllerRef.current.signal,
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
                            const eventType = event.type as string;

                            // O(1) lookup using dispatch table
                            const handler = EVENT_HANDLERS.get(eventType);
                            if (handler) {
                                handler(event, context);
                            }
                        } catch (e) {
                            console.error("Parse error:", e);
                        }
                    }
                }
            }

            // Clean up localStorage after successful completion
            localStorage.removeItem(`task-${taskId}`);

            // Mark all steps as completed
            const completedSteps = currentStepsRef.current.map(s => ({ ...s, status: "completed" as const }));
            updateTaskSteps(taskId, completedSteps);

            updateTaskStatus(taskId, "completed");
            endProgress();
        } catch (err) {
            // Don't report abort errors
            if (err instanceof Error && err.name === "AbortError") {
                console.log("[ResearchProgress] Request aborted");
                return;
            }
            console.error("Research error:", err);
            const errorMsg = tChat("connectionError");
            setError(errorMsg);
            updateTaskStatus(taskId, "failed", errorMsg);
            addEvent({
                type: "error",
                data: errorMsg,
            });
            endProgress();
        } finally {
            setIsResearching(false);
            abortControllerRef.current = null;
        }
    }, [taskId, updateTaskStatus, updateTaskSteps, updateTaskSources, updateTaskResult, tChat, startProgress, addEvent, endProgress]);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            if (abortControllerRef.current) {
                abortControllerRef.current.abort();
            }
            // Clean up localStorage if task wasn't completed
            const storedTaskInfo = localStorage.getItem(`task-${taskId}`);
            if (storedTaskInfo) {
                // Don't remove - let user retry later
                console.log("[ResearchProgress] Component unmounting with pending task");
            }
        };
    }, [taskId]);

    // Start research when task info is loaded
    useEffect(() => {
        if (taskInfo && !hasStarted && !isExistingTask) {
            setHasStarted(true);
            startResearch(taskInfo);
        }
    }, [taskInfo, hasStarted, isExistingTask, startResearch]);

    const handleBack = () => {
        router.push("/");
    };

    const handleRetry = () => {
        if (taskInfo) {
            setHasStarted(true);
            setIsExistingTask(false);
            startResearch(taskInfo);
        }
    };

    // Error state - task not found
    if (error && !taskInfo) {
        return (
            <div className="flex-1 flex items-center justify-center">
                <div className="text-center">
                    <AlertCircle className="w-12 h-12 text-destructive mx-auto mb-4" />
                    <h2 className="text-lg font-semibold text-foreground mb-2">{t("taskNotFound")}</h2>
                    <p className="text-sm text-muted-foreground mb-4">{error}</p>
                    <button
                        onClick={handleBack}
                        className="px-4 py-2 bg-foreground text-background rounded-lg hover:bg-foreground/90 transition-colors"
                    >
                        {t("goHome")}
                    </button>
                </div>
            </div>
        );
    }

    // Loading state - waiting for task info
    if (!taskInfo) {
        return (
            <div className="flex-1 flex items-center justify-center">
                <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
        );
    }

    return (
        <div className="flex-1 flex overflow-hidden">
            {/* Main content */}
            <div className="flex-1 flex flex-col overflow-hidden">
                <div className="px-4 md:px-6 py-3 md:py-4 border-b border-border">
                    <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                        <div className="flex items-center gap-3 md:gap-4 min-w-0">
                            <button
                                onClick={handleBack}
                                className="shrink-0 p-2 text-muted-foreground hover:text-foreground hover:bg-secondary rounded-lg transition-colors"
                            >
                                <ArrowLeft className="w-5 h-5" />
                            </button>
                            <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-2 mb-1">
                                    {SCENARIO_ICONS[taskInfo.scenario]}
                                    <span className="text-xs text-muted-foreground uppercase tracking-wider">
                                        {tResearch(`${taskInfo.scenario}.name`)}
                                    </span>
                                </div>
                                <h2 className="text-base md:text-lg font-semibold text-foreground truncate">{taskInfo.query}</h2>
                                <p className="text-sm text-muted-foreground">
                                    {error ? (
                                        <span className="text-destructive">{t("researchFailed")}</span>
                                    ) : isResearching ? (
                                        t("researching")
                                    ) : (
                                        t("researchComplete")
                                    )}
                                </p>
                            </div>
                        </div>

                        {/* Action Buttons */}
                        {!isResearching && researchResult && (
                            <div className="flex items-center gap-2 animate-in fade-in duration-300">
                                <button className="p-2 rounded-lg bg-secondary text-foreground hover:bg-secondary/80 transition-colors">
                                    <Share2 className="w-3.5 h-3.5" />
                                </button>
                            </div>
                        )}
                    </div>
                </div>

                {/* Browser Stream Viewer */}
                {browserStream && (
                    <div className="border-b border-border/50">
                        {/* Header - matching sidebar-agent-progress style */}
                        <div className="flex items-center justify-between px-3 h-10 border-b border-border/30 shrink-0">
                            <div className="flex items-center gap-2 min-w-0">
                                <Monitor className="w-4 h-4 text-foreground flex-shrink-0" />
                                <span className="text-sm font-medium truncate">Live Browser</span>
                                <span className="text-xs text-muted-foreground/60">
                                    {browserStream.sandboxId.slice(0, 8)}...
                                </span>
                            </div>
                            <div className="flex items-center shrink-0">
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-8 w-8"
                                    onClick={() => setShowBrowserStream(!showBrowserStream)}
                                >
                                    {showBrowserStream ? (
                                        <PanelRightClose className="w-4 h-4" />
                                    ) : (
                                        <PanelRight className="w-4 h-4" />
                                    )}
                                </Button>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-8 w-8"
                                    onClick={() => setBrowserStream(null)}
                                >
                                    <X className="w-4 h-4" />
                                </Button>
                            </div>
                        </div>
                        {/* Current browser action - what's happening in the live view */}
                        {currentStage?.startsWith("browser_") && currentStageDescription && (
                            <div className="px-3 py-1.5 text-xs text-muted-foreground border-b border-border/30 truncate">
                                {currentStageDescription}
                            </div>
                        )}
                        {/* Stream iframe - use streamUrl with authKey for E2B */}
                        {showBrowserStream && (
                            <ResearchBrowserStreamIframe stream={browserStream} />
                        )}
                    </div>
                )}

                <div className="flex-1 overflow-y-auto">
                    <div className="max-w-none mx-auto px-4 md:px-6 py-4 md:py-6">
                        {/* Live progress panel - shown during research */}
                        {isResearching && progressEvents.length > 0 && (
                            <div className="max-w-3xl mx-auto mb-6">
                                <TaskProgressPanel
                                    events={progressEvents as TimestampedEvent[]}
                                    sources={progressSources}
                                    isStreaming={isResearching}
                                    agentType="research"
                                />
                            </div>
                        )}

                        {error ? (
                            <div className="flex items-center justify-center min-h-[40vh]">
                                <div className="text-center">
                                    <AlertCircle className="w-8 h-8 text-destructive mx-auto mb-3" />
                                    <p className="text-sm text-muted-foreground">{error}</p>
                                    <button
                                        onClick={handleRetry}
                                        className="mt-4 px-4 py-2 bg-foreground text-background rounded-lg hover:bg-foreground/90 transition-colors text-sm"
                                    >
                                        {t("retry")}
                                    </button>
                                </div>
                            </div>
                        ) : researchResult ? (
                            <ResearchResultView
                                content={typeof researchResult === "string"
                                    ? researchResult
                                    : Array.isArray(researchResult)
                                        ? researchResult.map((item) => typeof item === "string" ? item : String(item)).join("")
                                        : String(researchResult)}
                                isStreaming={isResearching}
                                title={taskInfo.query}
                            />
                        ) : (
                            <div className="flex items-center justify-center min-h-[40vh]">
                                <div className="text-center">
                                    <Loader2 className="w-8 h-8 animate-spin text-foreground mx-auto mb-3" />
                                    <p className="text-sm text-muted-foreground">{t("generatingReport")}</p>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
