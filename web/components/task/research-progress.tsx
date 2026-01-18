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
    Check,
    Copy,
    Share2,
    ArrowLeft,
    AlertCircle,
} from "lucide-react";
import { ResearchResultView } from "@/components/query/research-report-view";
import { useTaskStore } from "@/lib/stores/task-store";
import { useAgentProgressStore } from "@/lib/stores/agent-progress-store";
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

    // Agent progress store for unified progress display
    const { startProgress, addEvent, endProgress } = useAgentProgressStore();

    const [taskInfo, setTaskInfo] = useState<TaskInfo | null>(null);
    const [isResearching, setIsResearching] = useState(false);
    const [researchResult, setResearchResult] = useState<string | unknown[]>("");
    const [error, setError] = useState<string | null>(null);
    const [hasStarted, setHasStarted] = useState(false);
    const [isExistingTask, setIsExistingTask] = useState(false);
    const [copied, setCopied] = useState(false);

    const handleCopyReport = async () => {
        if (!researchResult || !taskInfo) return;
        const resultString = typeof researchResult === "string"
            ? researchResult
            : Array.isArray(researchResult)
                ? researchResult.map((item) => typeof item === "string" ? item : String(item)).join("")
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
                const existingTask = tasks.find((task) => task.id === taskId);
                if (existingTask) {
                    console.log(`[ResearchProgress] Loading existing task ${taskId} from store`);
                    setTaskInfo({
                        query: existingTask.query,
                        scenario: existingTask.scenario,
                        depth: existingTask.depth,
                    });
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
                        interface StepData { id: string; type: string; description: string; status: string; }
                        const mappedSteps = (data.steps as StepData[]).map((s) => ({
                            id: s.id,
                            type: s.type,
                            description: s.description,
                            status: s.status,
                        }));
                        // Deduplicate steps
                        const uniqueSteps = mappedSteps.reduce((acc: StepData[], step) => {
                            const existingIndex = acc.findIndex((s) => s.type === step.type);
                            if (existingIndex >= 0) {
                                acc[existingIndex] = step;
                            } else {
                                acc.push(step);
                            }
                            return acc;
                        }, []);
                        updateTaskSteps(taskId, uniqueSteps as ResearchStep[]);
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
    }, [taskId, hasHydrated, tasks, createTask, setActiveTask, updateTaskSteps, updateTaskSources, updateTaskResult, t]);

    // Memoize startResearch to avoid recreation
    const startResearch = useCallback(async (info: TaskInfo) => {
        setIsResearching(true);
        setResearchResult("");
        setError(null);

        // Initialize steps in task store
        updateTaskSteps(taskId, [...INITIAL_STEPS]);
        updateTaskStatus(taskId, "running");

        // Start agent progress tracking
        startProgress(taskId, "research");

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
                    task_id: taskId, // Use frontend taskId so backend uses the same ID
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

                            if (event.type === "task_started") {
                                // Backend sends task_started with its own task_id
                                // We use this to ensure status is "running"
                                const backendTaskId = event.task_id;
                                if (backendTaskId) {
                                    console.log(`[ResearchProgress] Backend task started: ${backendTaskId}`);
                                }
                                // Ensure our task is marked as running
                                updateTaskStatus(taskId, "running");
                            } else if (event.type === "stage") {
                                // Backend sends stage events with "name" field for the step type
                                const stepName = event.name || event.data?.name;
                                const stepStatus = event.status || event.data?.status;
                                if (stepName && stepStatus) {
                                    // Update the status of the matching step type
                                    currentSteps = currentSteps.map((s) =>
                                        s.type === stepName ? { ...s, status: stepStatus } : s
                                    );
                                    updateTaskSteps(taskId, currentSteps);

                                    // Add to agent progress store
                                    const stepInfo = INITIAL_STEPS.find(s => s.type === stepName);
                                    addEvent({
                                        type: "stage",
                                        name: stepName,
                                        description: event.description || stepInfo?.description || stepName,
                                        status: stepStatus,
                                    });
                                }
                            } else if (event.type === "source") {
                                // Source events can have fields directly on the event OR nested in data (worker format)
                                const sourceData = event.data || event;
                                const newSource: Source = {
                                    id: sourceData.id || event.id || `source-${currentSources.length}`,
                                    title: sourceData.title || event.title || "Source",
                                    url: sourceData.url || event.url || "",
                                    snippet: sourceData.snippet || event.snippet,
                                };
                                currentSources = [...currentSources, newSource];
                                updateTaskSources(taskId, currentSources);

                                // Add source event to agent progress store
                                addEvent({
                                    type: "source",
                                    name: newSource.title,
                                    data: {
                                        id: newSource.id,
                                        title: newSource.title,
                                        url: newSource.url,
                                        snippet: newSource.snippet,
                                    },
                                });
                            } else if (event.type === "tool_call") {
                                // Handle tool call events
                                const toolName = event.tool || "tool";
                                const toolArgs = event.args || {};
                                addEvent({
                                    type: "tool_call",
                                    tool: toolName,
                                    args: toolArgs,
                                    id: event.id,
                                });
                            } else if (event.type === "tool_result") {
                                // Handle tool result events
                                addEvent({
                                    type: "tool_result",
                                    tool: event.tool,
                                    id: event.id,
                                    data: event.output || event.data,
                                });
                            } else if (event.type === "routing") {
                                // Handle routing decision events
                                addEvent({
                                    type: "routing",
                                    name: event.agent || event.selected_agent,
                                    data: event,
                                });
                            } else if (event.type === "handoff") {
                                // Handle agent handoff events
                                addEvent({
                                    type: "handoff",
                                    name: event.target,
                                    data: event,
                                });
                            } else if (event.type === "token") {
                                // Token content can be in data or content field
                                const tokenContent = event.data || event.content || "";
                                if (tokenContent) {
                                    fullResult += typeof tokenContent === "string" ? tokenContent : String(tokenContent);
                                    setResearchResult(fullResult);
                                    updateTaskResult(taskId, fullResult);
                                }
                            } else if (event.type === "error") {
                                const errorMsg = event.data || event.message || "Unknown error";
                                setError(errorMsg);
                                updateTaskStatus(taskId, "failed", errorMsg);
                                addEvent({
                                    type: "error",
                                    data: errorMsg,
                                });
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
            updateTaskSteps(taskId, completedSteps);

            updateTaskStatus(taskId, "completed");
            endProgress();
        } catch (err) {
            console.error("Research error:", err);
            setError(tChat("connectionError"));
            updateTaskStatus(taskId, "failed", tChat("connectionError"));
            addEvent({
                type: "error",
                data: tChat("connectionError"),
            });
            endProgress();
        } finally {
            setIsResearching(false);
        }
    }, [taskId, updateTaskStatus, updateTaskSteps, updateTaskSources, updateTaskResult, tChat, startProgress, addEvent, endProgress]);

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
