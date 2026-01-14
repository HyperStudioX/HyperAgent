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
  const [researchResult, setResearchResult] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [hasStarted, setHasStarted] = useState(false);
  const [isExistingTask, setIsExistingTask] = useState(false);
  const [progressPanelOpen, setProgressPanelOpen] = useState(false);

  // Load task from store or localStorage after hydration
  useEffect(() => {
    // Wait for store to hydrate
    if (!hasHydrated) {
      return;
    }

    // First check if task exists in store (returning to completed task)
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

      // If task is still running or pending, we need to restart
      if (existingTask.status === "running" || existingTask.status === "pending") {
        setHasStarted(false);
      } else {
        setHasStarted(true);
        setIsResearching(false);
      }
      return;
    }

    // Check localStorage for new task (only if task doesn't exist in store)
    const storedTaskInfo = localStorage.getItem(`task-${taskId}`);
    if (storedTaskInfo) {
      const info = JSON.parse(storedTaskInfo) as TaskInfo;
      setTaskInfo(info);
      // Create task in store - remove localStorage entry immediately to prevent duplicates
      localStorage.removeItem(`task-${taskId}`);
      createTask(taskId, info.query, info.scenario, info.depth);
      setActiveTask(taskId);
    } else {
      setError(t("taskNotFoundMessage"));
    }
  }, [taskId, hasHydrated, tasks, createTask, setActiveTask, t]);

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
                fullResult += event.data;
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

  // Loading state - wait for hydration
  if (!hasHydrated) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

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
          <div className="max-w-3xl mx-auto px-4 md:px-6 py-4 md:py-6">
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
                content={researchResult}
                isStreaming={isResearching}
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
          "flex flex-col bg-card",
          // Desktop: sidebar
          "md:w-72 md:border-l md:border-border md:relative",
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
        <div className="px-4 py-3 border-b border-border flex items-center justify-between">
          <h3 className="text-sm font-medium text-foreground">{t("progress")}</h3>
          {/* Mobile close button */}
          <button
            onClick={() => setProgressPanelOpen(false)}
            className="md:hidden p-1.5 -mr-1.5 text-muted-foreground hover:text-foreground rounded-lg hover:bg-secondary transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
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
      </div>
    </div>
  );
}
