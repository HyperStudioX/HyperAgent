"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import {
    Loader2,
    GraduationCap,
    TrendingUp,
    Code2,
    Newspaper,
    Globe,
    ExternalLink,
    CheckCircle2,
    Circle,
    ArrowLeft,
    AlertCircle,
    X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { ResearchResultView } from "@/components/query/research-result-view";
import { useTaskStore } from "@/lib/stores/task-store";
import type { ResearchStep, Source, ResearchScenario } from "@/lib/types";

const SCENARIO_ICONS: Record<ResearchScenario, React.ReactNode> = {
    academic: <GraduationCap className="w-4 h-4" />,
    market: <TrendingUp className="w-4 h-4" />,
    technical: <Code2 className="w-4 h-4" />,
    news: <Newspaper className="w-4 h-4" />,
};

// Define all research steps upfront
const INITIAL_STEPS: ResearchStep[] = [
    { id: "1", type: "search", description: "Searching", status: "pending" },
    { id: "2", type: "analyze", description: "Analyzing", status: "pending" },
    { id: "3", type: "synthesize", description: "Synthesizing", status: "pending" },
    { id: "4", type: "write", description: "Writing", status: "pending" },
];

interface TaskInfo {
    query: string;
    scenario: ResearchScenario;
    depth: string;
}

interface TaskProgressProps {
    taskId: string;
}

export function TaskProgress({ taskId }: TaskProgressProps) {
    const router = useRouter();
    const t = useTranslations("task");
    const tResearch = useTranslations("research");
    const tChat = useTranslations("chat");

    const {
        tasks,
        hasHydrated,
        createTask,
        updateTaskStatus,
        updateTaskSteps,
        updateTaskSources,
        updateTaskResult,
        setActiveTask,
    } = useTaskStore();

    const [taskInfo, setTaskInfo] = useState<TaskInfo | null>(null);
    const [isResearching, setIsResearching] = useState(false);
    const [steps, setSteps] = useState<ResearchStep[]>([]);
    const [sources, setSources] = useState<Source[]>([]);
    const [researchResult, setResearchResult] = useState<string | any[]>("");
    const [error, setError] = useState<string | null>(null);
    const [hasStarted, setHasStarted] = useState(false);
    const [isExistingTask, setIsExistingTask] = useState(false);
    const [progressPanelOpen, setProgressPanelOpen] = useState(false);
    // Start expanded when running, will collapse when report is ready
    const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
    const [hasAutoCollapsed, setHasAutoCollapsed] = useState(false);

    // Load task from store or API
    useEffect(() => {
        console.log(`[TaskProgress] Fetching task ${taskId} from API...`);
        const fetchTask = async () => {
            try {
                // Always try to fetch fresh data from the API first
                // Use /result endpoint to get full task data including report, steps, and sources
                const response = await fetch(`/api/v1/tasks/${taskId}/result`);
                console.log(`[TaskProgress] API response status: ${response.status} for task ${taskId}`);
                if (response.ok) {
                    const data = await response.json();
                    console.log(`[TaskProgress] Task data received:`, data);

                    // Update store with fresh data
                    setTaskInfo({
                        query: data.query,
                        scenario: data.scenario,
                        depth: data.depth,
                    });

                    // Map steps and sources from backend format to frontend format
                    if (data.steps) {
                        const mappedSteps = data.steps.map((s: any) => ({
                            id: s.id,
                            type: s.type,
                            description: s.description,
                            status: s.status,
                        }));
                        // Deduplicate steps by type, keeping the latest one (last in array)
                        const uniqueSteps = mappedSteps.reduce((acc: typeof mappedSteps, step: typeof mappedSteps[0]) => {
                            const existingIndex = acc.findIndex((s: typeof step) => s.type === step.type);
                            if (existingIndex >= 0) {
                                acc[existingIndex] = step; // Replace with latest
                            } else {
                                acc.push(step);
                            }
                            return acc;
                        }, []);
                        setSteps(uniqueSteps);
                        updateTaskSteps(taskId, uniqueSteps);
                    }

                    if (data.sources) {
                        const mappedSources = data.sources.map((s: any) => ({
                            id: s.id,
                            title: s.title,
                            url: s.url,
                            snippet: s.snippet,
                        }));
                        // Deduplicate sources by URL
                        const uniqueSources = mappedSources.reduce((acc: typeof mappedSources, source: typeof mappedSources[0]) => {
                            if (!acc.some((s: typeof source) => s.url === source.url)) {
                                acc.push(source);
                            }
                            return acc;
                        }, []);
                        setSources(uniqueSources);
                        updateTaskSources(taskId, uniqueSources);
                    }

                    if (data.report) {
                        setResearchResult(data.report);
                        updateTaskResult(taskId, data.report);
                    }

                    setError(data.error || null);
                    setIsExistingTask(true);
                    setActiveTask(taskId);

                    // If task is still active, we need to handle it accordingly
                    // (But usually the backend list only shows completed or failed tasks if we aren't streaming)
                    if (data.status === "completed") {
                        setHasStarted(true);
                        setIsResearching(false);
                    } else if (data.status === "failed") {
                        setHasStarted(true);
                        setIsResearching(false);
                    } else {
                        // For pending/running/queued
                        setHasStarted(false);
                    }
                    return;
                } else {
                    console.warn(`[TaskProgress] API returned non-OK status ${response.status} for task ${taskId}`);
                    const errorText = await response.text().catch(() => "Unknown error");
                    console.warn(`[TaskProgress] Error response:`, errorText);
                }
            } catch (err) {
                console.error("[TaskProgress] API fetch failed:", err);
            }

            // Fallback to local store if API fails (only if store is hydrated)
            if (hasHydrated) {
                const existingTask = tasks.find((t) => t.id === taskId);

                if (existingTask) {
                    setTaskInfo({
                        query: existingTask.query,
                        scenario: existingTask.scenario,
                        depth: existingTask.depth,
                    });
                    setSteps(existingTask.steps);
                    setSources(existingTask.sources);
                    setResearchResult(existingTask.result);
                    setError(existingTask.error || null);
                    setIsExistingTask(true);
                    setActiveTask(taskId);

                    if (existingTask.status === "running" || existingTask.status === "pending") {
                        setHasStarted(false);
                    } else {
                        setHasStarted(true);
                        setIsResearching(false);
                    }
                    return;
                }
            }

            // Check localStorage for new task
            const storedTaskInfo = localStorage.getItem(`task-${taskId}`);
            if (storedTaskInfo) {
                const info = JSON.parse(storedTaskInfo) as TaskInfo;
                setTaskInfo(info);
                localStorage.removeItem(`task-${taskId}`);
                createTask(taskId, info.query, info.scenario, info.depth);
                setActiveTask(taskId);
            } else {
                setError(t("taskNotFoundMessage"));
            }
        };

        fetchTask();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [taskId]); // Only depend on taskId - API call should happen immediately on mount/taskId change

    // Memoize startResearch to avoid recreation
    const startResearch = useCallback(async (info: TaskInfo) => {
        setIsResearching(true);
        // Initialize all steps as pending
        setSteps([...INITIAL_STEPS]);
        setSources([]);
        setResearchResult("");
        setError(null);

        updateTaskStatus(taskId, "running");

        let currentSteps: ResearchStep[] = [...INITIAL_STEPS];
        let currentSources: Source[] = [];

        try {
            const response = await fetch("/api/v1/query/stream", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: info.query,
                    mode: "research",
                    scenario: info.scenario,
                    depth: info.depth,
                }),
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);

            const reader = response.body?.getReader();
            if (!reader) throw new Error("No response body");

            const decoder = new TextDecoder();
            let buffer = "";
            let fullResult = "";

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

                            if (event.type === "step") {
                                const stepData = event.data;
                                // Update the status of the matching step type
                                currentSteps = currentSteps.map((s) =>
                                    s.type === stepData.type ? { ...s, status: stepData.status } : s
                                );
                                setSteps([...currentSteps]);
                                updateTaskSteps(taskId, currentSteps);
                            } else if (event.type === "source") {
                                const sourceData = event.data;
                                const newSource = {
                                    id: sourceData.id,
                                    title: sourceData.title,
                                    url: sourceData.url,
                                    snippet: sourceData.snippet,
                                };
                                currentSources = [...currentSources, newSource];
                                setSources([...currentSources]);
                                updateTaskSources(taskId, currentSources);
                            } else if (event.type === "token") {
                                const tokenContent = typeof event.data === "string" ? event.data : String(event.data);
                                fullResult += tokenContent;
                                setResearchResult(fullResult);
                                updateTaskResult(taskId, fullResult);
                            } else if (event.type === "error") {
                                setError(event.data);
                                updateTaskStatus(taskId, "failed", event.data);
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
            const completedSteps = currentSteps.map(s => ({ ...s, status: "completed" as const }));
            setSteps(completedSteps);
            updateTaskSteps(taskId, completedSteps);

            updateTaskStatus(taskId, "completed");
        } catch (err) {
            console.error("Research error:", err);
            setError(tChat("connectionError"));
            updateTaskStatus(taskId, "failed", tChat("connectionError"));
        } finally {
            setIsResearching(false);
        }
    }, [taskId, updateTaskStatus, updateTaskSteps, updateTaskSources, updateTaskResult, tChat]);

    // Start research when task info is loaded
    useEffect(() => {
        if (taskInfo && !hasStarted && !isExistingTask) {
            setHasStarted(true);
            startResearch(taskInfo);
        }
    }, [taskInfo, hasStarted, isExistingTask, startResearch]);

    // Auto-collapse sidebar when report is ready (task completed)
    useEffect(() => {
        // If researching, ensure sidebar is expanded
        if (isResearching) {
            setIsSidebarCollapsed(false);
            setHasAutoCollapsed(false);
            return;
        }

        // Auto-collapse when report is generated (only once)
        const hasReport = typeof researchResult === "string"
            ? researchResult.length > 0
            : Array.isArray(researchResult) && researchResult.length > 0;

        if (hasReport && !hasAutoCollapsed && !error) {
            setIsSidebarCollapsed(true);
            setHasAutoCollapsed(true);
        }
    }, [isResearching, researchResult, hasAutoCollapsed, error]);

    const handleBack = () => {
        router.push("/");
    };

    const handleRetry = () => {
        if (taskInfo) {
            setHasStarted(true);
            setIsExistingTask(false);
            setHasAutoCollapsed(false); // Reset so sidebar stays expanded during retry
            setIsSidebarCollapsed(false); // Expand sidebar for retry
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
                        {/* Mobile toggle for progress panel */}
                        <button
                            onClick={() => setProgressPanelOpen(!progressPanelOpen)}
                            className="md:hidden px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground bg-secondary hover:bg-secondary/80 rounded-lg transition-colors self-start"
                        >
                            {t("progress")} ({steps.length})
                        </button>
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto">
                    <div className="max-w-none mx-auto px-4 md:px-6 py-4 md:py-6">
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
                                        ? (researchResult as any[]).map((item: any) => typeof item === "string" ? item : String(item)).join("")
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

            {/* Mobile backdrop */}
            {progressPanelOpen && (
                <div
                    className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40 md:hidden transition-opacity"
                    onClick={() => setProgressPanelOpen(false)}
                />
            )}

            {/* Progress sidebar */}
            <div
                className={cn(
                    "flex flex-col bg-card border-l border-border bg-zinc-50 dark:bg-zinc-900/50",
                    // Desktop: sidebar
                    "md:relative transition-all duration-300 ease-in-out",
                    isSidebarCollapsed ? "md:w-[60px]" : "md:w-80",
                    // Mobile: bottom sheet
                    "fixed bottom-0 left-0 right-0 z-50",
                    "md:translate-y-0", // Always visible on desktop
                    "max-h-[70vh] md:max-h-none",
                    "rounded-t-2xl md:rounded-none",
                    "shadow-2xl md:shadow-none",
                    "border-t border-border md:border-t-0",
                    "transition-transform duration-300 ease-out",
                    progressPanelOpen ? "translate-y-0" : "translate-y-full md:translate-y-0"
                )}
            >
                <div className={cn(
                    "px-4 py-3 border-b border-border flex items-center h-14",
                    isSidebarCollapsed ? "justify-center" : "justify-between"
                )}>
                    {!isSidebarCollapsed && (
                        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t("progress")}</h3>
                    )}

                    {/* Desktop toggle button */}
                    <button
                        onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
                        className="hidden md:flex p-1.5 hover:bg-secondary/80 rounded-md text-muted-foreground hover:text-foreground transition-colors"
                        title={isSidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
                    >
                        {isSidebarCollapsed ? (
                            <ArrowLeft className="w-4 h-4 rotate-180" />
                        ) : (
                            <ArrowLeft className="w-4 h-4" />
                        )}
                    </button>

                    {/* Mobile close button */}
                    <button
                        onClick={() => setProgressPanelOpen(false)}
                        className="md:hidden p-1.5 -mr-1.5 text-muted-foreground hover:text-foreground rounded-lg hover:bg-secondary transition-colors"
                    >
                        <X className="w-4 h-4" />
                    </button>
                </div>

                {!isSidebarCollapsed && (
                    <div className="flex-1 overflow-y-auto animate-in fade-in duration-300">
                        <div className="p-4 space-y-6">
                            {/* Steps */}
                            <div className="space-y-3">
                                {steps.map((step) => (
                                    <div key={step.id} className="flex items-center gap-3">
                                        <div className="relative">
                                            {step.status === "completed" ? (
                                                <CheckCircle2 className="w-5 h-5 text-green-500 animate-bounce-in" />
                                            ) : step.status === "running" ? (
                                                <Loader2 className="w-5 h-5 text-foreground animate-spin" />
                                            ) : step.status === "failed" ? (
                                                <AlertCircle className="w-5 h-5 text-destructive animate-scale-in" />
                                            ) : (
                                                <Circle className="w-5 h-5 text-muted-foreground/40" />
                                            )}
                                        </div>
                                        <span className={cn(
                                            "text-sm",
                                            step.status === "completed" && "text-foreground",
                                            step.status === "running" && "text-foreground font-medium",
                                            step.status === "failed" && "text-destructive",
                                            step.status === "pending" && "text-muted-foreground/60"
                                        )}>
                                            {t(`steps.${step.type}.${step.status}`)}
                                        </span>
                                    </div>
                                ))}
                            </div>

                            {/* Sources */}
                            {sources.length > 0 && (
                                <div className="pt-4 border-t border-border">
                                    <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">
                                        {t("sources")} ({sources.length})
                                    </h4>
                                    <div className="space-y-2">
                                        {sources.map((source) => (
                                            <a
                                                key={source.id}
                                                href={source.url}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="group flex items-start gap-2 p-2 rounded-lg hover:bg-secondary/50 transition-colors"
                                            >
                                                <Globe className="w-4 h-4 text-muted-foreground shrink-0 mt-0.5" />
                                                <div className="flex-1 min-w-0">
                                                    <div className="text-sm text-foreground truncate group-hover:text-muted-foreground transition-colors">
                                                        {source.title}
                                                    </div>
                                                    {source.snippet && (
                                                        <div className="text-xs text-muted-foreground/60 line-clamp-2 mt-0.5">
                                                            {source.snippet}
                                                        </div>
                                                    )}
                                                </div>
                                                <ExternalLink className="w-3 h-3 text-muted-foreground/40 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
                                            </a>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
