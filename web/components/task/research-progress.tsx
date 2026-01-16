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
    Check,
    Copy,
    Share2,
    ArrowLeft,
    AlertCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { ResearchResultView } from "@/components/query/research-report-view";
import { useTaskStore } from "@/lib/stores/task-store";
import { MenuToggle } from "@/components/ui/menu-toggle";
import type { ResearchStep, Source, ResearchScenario } from "@/lib/types";

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

interface ResearchProgressProps {
    taskId: string;
}

export function ResearchProgress({ taskId }: ResearchProgressProps) {
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
    const [copied, setCopied] = useState(false);

    const handleCopyReport = async () => {
        if (!researchResult || !taskInfo) return;
        const resultString = typeof researchResult === "string"
            ? researchResult
            : Array.isArray(researchResult)
                ? (researchResult as any[]).map((item: any) => typeof item === "string" ? item : String(item)).join("")
                : String(researchResult);

        const textToCopy = `# ${taskInfo.query}\n\n${resultString}`;
        await navigator.clipboard.writeText(textToCopy);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    // Load task from store or API
    useEffect(() => {
        const fetchTask = async () => {
            // 1. Check localStorage for NEW task first (just submitted from Home)
            const storedTaskInfo = localStorage.getItem(`task-${taskId}`);
            if (storedTaskInfo) {
                console.log(`[ResearchProgress] New task detected in local storage for ${taskId}`);
                try {
                    const info = JSON.parse(storedTaskInfo) as TaskInfo;
                    setTaskInfo(info);
                    // Don't remove from localStorage yet, startResearch will handle final cleanup
                    // Note: startResearch is triggered by the taskInfo being set

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

            // 2. Fallback to Task Store if hydrated
            if (hasHydrated) {
                const existingTask = tasks.find((t) => t.id === taskId);
                if (existingTask) {
                    console.log(`[ResearchProgress] Loading existing task ${taskId} from store`);
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

                    if (existingTask.status !== "running" && existingTask.status !== "pending") {
                        setHasStarted(true);
                        setIsResearching(false);
                    }
                    return;
                }
            }

            // 3. Otherwise fetch from API (existing task from history)
            console.log(`[ResearchProgress] Fetching task ${taskId} from API...`);
            try {
                // Use /result endpoint to get full task data including report, steps, and sources
                const response = await fetch(`/api/v1/tasks/${taskId}/result`);
                if (response.ok) {
                    const data = await response.json();
                    console.log(`[ResearchProgress] Task data received from API:`, data);

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
                        // Deduplicate steps
                        const uniqueSteps = mappedSteps.reduce((acc: any[], step: any) => {
                            const existingIndex = acc.findIndex((s: any) => s.type === step.type);
                            if (existingIndex >= 0) {
                                acc[existingIndex] = step;
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
                        setSources(mappedSources);
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
                } else {
                    console.warn(`[ResearchProgress] API returned status ${response.status}`);
                    setError("Failed to load task details");
                }
            } catch (err) {
                console.error("[ResearchProgress] API fetch failed:", err);
                setError("Connection error while loading task");
            }
        };

        fetchTask();
    }, [taskId, hasHydrated, createTask, setActiveTask, updateTaskSteps, updateTaskSources, updateTaskResult, t]);

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

                            if (event.type === "stage") {
                                // Backend sends stage events with "name" field for the step type
                                const stepName = event.name || event.data?.name;
                                const stepStatus = event.status || event.data?.status;
                                if (stepName && stepStatus) {
                                    // Update the status of the matching step type
                                    currentSteps = currentSteps.map((s) =>
                                        s.type === stepName ? { ...s, status: stepStatus } : s
                                    );
                                    setSteps([...currentSteps]);
                                    updateTaskSteps(taskId, currentSteps);
                                }
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

                        <div className="flex items-center gap-2">
                            {/* Action Buttons */}
                            {!isResearching && researchResult && (
                                <div className="hidden md:flex items-center gap-2 mr-2 animate-in fade-in duration-300">
                                    <button
                                        onClick={handleCopyReport}
                                        className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-secondary text-foreground hover:bg-secondary/80 transition-colors text-sm font-medium"
                                    >
                                        {copied ? (
                                            <Check className="w-3.5 h-3.5" strokeWidth={3} />
                                        ) : (
                                            <Copy className="w-3.5 h-3.5" />
                                        )}
                                        <span>{copied ? "Copied" : "Copy"}</span>
                                    </button>
                                    <button className="p-2 rounded-lg bg-secondary text-foreground hover:bg-secondary/80 transition-colors">
                                        <Share2 className="w-3.5 h-3.5" />
                                    </button>
                                </div>
                            )}

                            {/* Mobile toggle for progress panel */}
                            <button
                                onClick={() => setProgressPanelOpen(!progressPanelOpen)}
                                className="md:hidden px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground bg-secondary hover:bg-secondary/80 rounded-lg transition-colors"
                            >
                                {t("progress")} ({steps.length})
                            </button>
                        </div>
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
                    className="fixed inset-0 bg-black/40 backdrop-blur-sm z-40 md:hidden transition-opacity"
                    onClick={() => setProgressPanelOpen(false)}
                />
            )}

            {/* Progress sidebar */}
            <div
                className={cn(
                    "flex flex-col bg-card border-l border-border",
                    // Desktop: sidebar
                    "md:relative transition-all duration-300 ease-in-out",
                    isSidebarCollapsed ? "md:w-[60px]" : "md:w-80",
                    // Mobile: bottom sheet
                    "fixed bottom-0 left-0 right-0 z-50",
                    "md:translate-y-0", // Always visible on desktop
                    "max-h-[70vh] md:max-h-none",
                    "rounded-t-xl md:rounded-none",
                    "md:shadow-none",
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
                    <div className="hidden md:block">
                        <MenuToggle
                            isOpen={!isSidebarCollapsed}
                            onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
                        />
                    </div>

                    {/* Mobile close button */}
                    <div className="md:hidden">
                        <MenuToggle
                            isOpen={true}
                            onClick={() => setProgressPanelOpen(false)}
                            className="p-2 -mr-2"
                        />
                    </div>
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
                                                <CheckCircle2 className="w-5 h-5 text-foreground animate-bounce-in" />
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
                                            {t(`steps.${step.type}.${step.status}`, { defaultValue: step.description })}
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
