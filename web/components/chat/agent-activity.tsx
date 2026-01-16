"use client";

import React, { useMemo, useState, useEffect } from "react";
import {
    Loader2,
    Check,
    ChevronDown,
    AlertCircle,
    Search,
    Wrench,
    Info,
    Brain,
    FileText,
    Code,
    PenTool,
    BarChart3,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";

interface AgentProgressProps {
    status?: string | null;
    agentEvents?: any[];
    isStreaming?: boolean;
    className?: string;
    mode?: string;
}

interface ProgressDetail {
    key: string;
    text: string;
    type: "info" | "tool" | "search" | "error";
    status?: "running" | "completed" | "failed";
}

interface StageItem {
    key: string;
    name: string;
    label: string;
    status: "running" | "completed" | "failed" | "pending";
    type: "stage" | "error";
    progress: ProgressDetail[];
    timestamp?: number;
}

// Stage icons by name
const STAGE_ICONS: Record<string, React.ReactNode> = {
    thinking: <Brain className="w-3.5 h-3.5" />,
    routing: <Brain className="w-3.5 h-3.5" />,
    chat: <Brain className="w-3.5 h-3.5" />,
    search: <Search className="w-3.5 h-3.5" />,
    tool: <Wrench className="w-3.5 h-3.5" />,
    analyze: <FileText className="w-3.5 h-3.5" />,
    synthesize: <FileText className="w-3.5 h-3.5" />,
    write: <PenTool className="w-3.5 h-3.5" />,
    generate: <Code className="w-3.5 h-3.5" />,
    execute: <Code className="w-3.5 h-3.5" />,
    plan: <Brain className="w-3.5 h-3.5" />,
    summarize: <FileText className="w-3.5 h-3.5" />,
    finalize: <Check className="w-3.5 h-3.5" />,
    outline: <FileText className="w-3.5 h-3.5" />,
    data: <BarChart3 className="w-3.5 h-3.5" />,
};

export function AgentProgress({ status, agentEvents, isStreaming, className, mode }: AgentProgressProps) {
    const t = useTranslations("chat.agent");
    const [isCollapsed, setIsCollapsed] = useState(false);
    const [hasCompletedOnce, setHasCompletedOnce] = useState(false);
    const [expandedStages, setExpandedStages] = useState<Set<string>>(new Set());

    const toggleStageExpand = (stageKey: string) => {
        setExpandedStages((prev) => {
            const next = new Set(prev);
            if (next.has(stageKey)) {
                next.delete(stageKey);
            } else {
                next.add(stageKey);
            }
            return next;
        });
    };

    const truncateText = (value: string, maxLength = 60) =>
        value.length > maxLength ? value.slice(0, maxLength) + "..." : value;

    const activityState = useMemo(() => {
        const stages: StageItem[] = [];
        const stageMap = new Map<string, StageItem>();
        let currentStage: StageItem | null = null;
        let detailCounter = 0; // Counter to ensure unique keys

        const normalizeStatus = (value: string | undefined): StageItem["status"] => {
            if (value === "completed") return "completed";
            if (value === "failed") return "failed";
            if (value === "pending") return "pending";
            return "running";
        };

        const getStageLabel = (name: string, status: string): string => {
            // Try i18n key: stages.{name}.{status}
            const stageKey = `stages.${name}.${status}`;
            try {
                const translated = t(stageKey as any);
                if (translated && translated !== stageKey) {
                    return translated;
                }
            } catch {
                // fallback to default stage
            }

            // Try default stage translations
            try {
                const defaultKey = `stages.default.${status}`;
                const defaultTranslated = t(defaultKey as any);
                if (defaultTranslated && defaultTranslated !== defaultKey) {
                    return defaultTranslated;
                }
            } catch {
                // final fallback
            }

            // Final fallback: capitalize name
            return name ? `${name.charAt(0).toUpperCase()}${name.slice(1)}...` : t("processing");
        };

        for (const event of agentEvents || []) {
            if (event.type === "stage") {
                const stepName = String(event.name || event.data?.name || "");
                const description = String(event.description || event.data?.description || "");
                const stepStatus = normalizeStatus(event.status || event.data?.status);
                const key = `stage:${stepName || "default"}`;

                if (stageMap.has(key)) {
                    const existing = stageMap.get(key)!;
                    // Stage is completing - update status and label
                    if (stepStatus === "completed" || stepStatus === "failed") {
                        existing.status = stepStatus;
                        existing.label = getStageLabel(stepName, stepStatus);
                        // Add completion description as final detail if different
                        if (description && description !== existing.name) {
                            existing.progress.push({
                                key: `detail:complete:${Date.now()}:${detailCounter++}`,
                                text: description,
                                type: "info",
                                status: "completed",
                            });
                        }
                        // Close current stage
                        currentStage = null;
                    }
                } else {
                    // New stage starting
                    const newStage: StageItem = {
                        key,
                        name: stepName,
                        label: getStageLabel(stepName, stepStatus),
                        status: stepStatus,
                        type: "stage",
                        progress: [],
                        timestamp: Date.now(),
                    };
                    // Add initial description as first progress item
                    if (description) {
                        newStage.progress.push({
                            key: `detail:start:${Date.now()}:${detailCounter++}`,
                            text: description,
                            type: "info",
                        });
                    }
                    stageMap.set(key, newStage);
                    stages.push(newStage);
                    currentStage = newStage;
                }
            } else if (event.type === "tool_call") {
                const toolName = event.tool || event.data?.tool || "";
                const query = event.args?.query || event.data?.args?.query || "";
                const isSearch = toolName === "web_search" || toolName === "google_search" || toolName === "web";

                const detail: ProgressDetail = {
                    key: `tool:${toolName}:${Date.now()}:${detailCounter++}`,
                    text: isSearch
                        ? query
                            ? t("searchingQuery", { query: truncateText(query) })
                            : t("searching")
                        : t("executing", { tool: toolName || "tool" }),
                    type: isSearch ? "search" : "tool",
                    status: "running",
                };

                if (currentStage) {
                    currentStage.progress.push(detail);
                } else {
                    // Create implicit stage for orphan tools
                    const implicitStage: StageItem = {
                        key: `stage:tool:${Date.now()}:${detailCounter++}`,
                        name: "tool",
                        label: isSearch ? t("stages.search.running") : t("processing"),
                        status: "running",
                        type: "stage",
                        progress: [detail],
                        timestamp: Date.now(),
                    };
                    stages.push(implicitStage);
                    stageMap.set(implicitStage.key, implicitStage);
                    currentStage = implicitStage;
                }
            } else if (event.type === "tool_result") {
                const toolName = event.tool || event.name || event.data?.tool || "";
                // Mark the last matching tool as completed
                if (currentStage) {
                    for (let i = currentStage.progress.length - 1; i >= 0; i--) {
                        const item = currentStage.progress[i];
                        if (item.status === "running" && item.key.includes(`tool:${toolName}`)) {
                            item.status = "completed";
                            break;
                        }
                    }
                }
            } else if (event.type === "error") {
                const errorMessage = event.error || event.message || event.data || "Unknown error";
                const errorDetail: ProgressDetail = {
                    key: `error:${Date.now()}:${detailCounter++}`,
                    text: truncateText(String(errorMessage)),
                    type: "error",
                    status: "failed",
                };
                if (currentStage) {
                    currentStage.progress.push(errorDetail);
                    currentStage.status = "failed";
                } else {
                    const errorStage: StageItem = {
                        key: `stage:error:${Date.now()}:${detailCounter++}`,
                        name: "error",
                        label: t("error"),
                        status: "failed",
                        type: "error",
                        progress: [errorDetail],
                        timestamp: Date.now(),
                    };
                    stages.push(errorStage);
                }
            }
        }

        // Calculate overall progress
        const totalStages = stages.length;
        const completedStages = stages.filter((s) => s.status === "completed").length;
        const hasRunning = stages.some((s) => s.status === "running");
        const hasFailed = stages.some((s) => s.status === "failed");

        return {
            stages,
            totalStages,
            completedStages,
            hasRunning,
            hasFailed,
            progress: totalStages > 0 ? Math.round((completedStages / totalStages) * 100) : 0,
        };
    }, [agentEvents, t]);

    // Auto-collapse when all stages complete
    useEffect(() => {
        if (!isStreaming && activityState.stages.length > 0 && !activityState.hasRunning && !hasCompletedOnce) {
            setHasCompletedOnce(true);
            // Delay collapse for smooth transition
            const timer = setTimeout(() => setIsCollapsed(true), 1000);
            return () => clearTimeout(timer);
        }
    }, [isStreaming, activityState.hasRunning, activityState.stages.length, hasCompletedOnce]);

    // Reset when new streaming starts
    useEffect(() => {
        if (isStreaming && hasCompletedOnce) {
            setHasCompletedOnce(false);
            setIsCollapsed(false);
        }
    }, [isStreaming, hasCompletedOnce]);

    const getStageIcon = (stage: StageItem) => {
        const baseIcon = STAGE_ICONS[stage.name] || <Info className="w-3.5 h-3.5" />;

        if (stage.status === "running") {
            return <Loader2 className="w-3.5 h-3.5 animate-spin text-foreground" />;
        }
        if (stage.status === "completed") {
            return <Check className="w-3.5 h-3.5 text-foreground" />;
        }
        if (stage.status === "failed") {
            return <AlertCircle className="w-3.5 h-3.5 text-destructive" />;
        }
        return <div className="text-muted-foreground/50">{baseIcon}</div>;
    };

    const getDetailIcon = (detail: ProgressDetail) => {
        if (detail.type === "search") {
            if (detail.status === "running") return <Loader2 className="w-3 h-3 animate-spin text-foreground" />;
            if (detail.status === "completed") return <Check className="w-3 h-3 text-foreground" />;
            return <Search className="w-3 h-3 text-muted-foreground" />;
        }
        if (detail.type === "tool") {
            if (detail.status === "running") return <Loader2 className="w-3 h-3 animate-spin text-foreground" />;
            if (detail.status === "completed") return <Check className="w-3 h-3 text-foreground" />;
            return <Wrench className="w-3 h-3 text-muted-foreground" />;
        }
        if (detail.type === "error") {
            return <AlertCircle className="w-3 h-3 text-destructive" />;
        }
        if (detail.status === "completed") {
            return <Check className="w-3 h-3 text-foreground" />;
        }
        return <Info className="w-3 h-3 text-muted-foreground" />;
    };

    if (activityState.stages.length === 0 && !isStreaming) {
        return null;
    }

    // Collapsed view - subtle styling following design system
    if (isCollapsed && !isStreaming) {
        const statusText = activityState.hasFailed ? t("completedWithErrors") : t("completed");
        const stagesText = t("completedStages", { count: activityState.completedStages });

        return (
            <button
                onClick={() => setIsCollapsed(false)}
                className={cn(
                    "mb-3 flex items-center gap-2 px-3 py-2 rounded-lg",
                    "bg-card border border-border",
                    "hover:bg-secondary/50 transition-colors",
                    "text-xs font-medium",
                    className
                )}
                aria-label={t("expandStage")}
                aria-expanded="false"
            >
                <ChevronDown className="w-3.5 h-3.5 -rotate-90 text-muted-foreground" />
                {activityState.hasFailed ? (
                    <>
                        <span className="flex items-center justify-center w-4 h-4 rounded-full bg-destructive text-white" aria-hidden="true">
                            <AlertCircle className="w-2.5 h-2.5" />
                        </span>
                        <span className="text-destructive">{statusText}</span>
                    </>
                ) : (
                    <>
                        <span className="flex items-center justify-center w-4 h-4 rounded-full bg-foreground text-background" aria-hidden="true">
                            <Check className="w-2.5 h-2.5" strokeWidth={3} />
                        </span>
                        <span className="text-muted-foreground">{stagesText}</span>
                    </>
                )}
            </button>
        );
    }

    return (
        <div className={cn("mb-4", className)}>
            {/* Header with collapse toggle - follows design system */}
            <button
                onClick={() => setIsCollapsed(!isCollapsed)}
                className={cn(
                    "w-full flex items-center justify-between gap-3 px-4 py-3 rounded-xl",
                    "bg-secondary border border-border",
                    "hover:bg-secondary/80 transition-colors",
                    "text-sm font-medium",
                    activityState.hasRunning && "ring-1 ring-foreground/50"
                )}
                aria-label={isCollapsed ? t("expandStage") : t("collapseStage")}
                aria-expanded={!isCollapsed}
            >
                <div className="flex items-center gap-3">
                    {activityState.hasRunning ? (
                        <span className="flex items-center justify-center w-5 h-5 rounded-full bg-foreground text-background">
                            <Loader2 className="w-3 h-3 animate-spin" />
                        </span>
                    ) : activityState.hasFailed ? (
                        <span className="flex items-center justify-center w-5 h-5 rounded-full bg-destructive text-white">
                            <AlertCircle className="w-3 h-3" />
                        </span>
                    ) : (
                        <span className="flex items-center justify-center w-5 h-5 rounded-full bg-foreground text-background">
                            <Check className="w-3 h-3" strokeWidth={3} />
                        </span>
                    )}
                    <span className="text-foreground">
                        {activityState.hasRunning
                            ? t("inProgress")
                            : activityState.hasFailed
                              ? t("completedWithErrors")
                              : t("completed")}
                    </span>
                    {activityState.stages.length > 0 && (
                        <span
                            className="text-xs px-2 py-0.5 rounded-full bg-muted text-muted-foreground"
                            aria-label={`${activityState.completedStages} of ${activityState.stages.length} stages completed`}
                        >
                            {activityState.completedStages}/{activityState.stages.length}
                        </span>
                    )}
                </div>
                <ChevronDown
                    className={cn(
                        "w-4 h-4 text-muted-foreground transition-transform duration-200",
                        isCollapsed && "-rotate-90"
                    )}
                />
            </button>

            {/* Stages list - subdued compared to header */}
            {!isCollapsed && (
                <div className="mt-3 ml-2 space-y-1 animate-in fade-in slide-in-from-top-1 duration-200">
                    {activityState.stages.length === 0 && isStreaming && (
                        <div className="flex items-center gap-2 py-1.5 px-3 rounded-md bg-muted/20">
                            <Loader2 className="w-3 h-3 animate-spin text-muted-foreground" />
                            <span className="text-xs text-muted-foreground">{t("thinking")}</span>
                        </div>
                    )}
                    {activityState.stages.map((stage) => {
                        const hasDetails = stage.progress.length > 0;
                        const isStageExpanded = expandedStages.has(stage.key);
                        
                        return (
                            <div key={stage.key} className="select-none">
                                {/* Stage row - clickable to expand details */}
                                <button
                                    onClick={() => hasDetails && toggleStageExpand(stage.key)}
                                    disabled={!hasDetails}
                                    className={cn(
                                        "w-full flex items-center gap-2 py-2 px-2.5 rounded-lg min-h-[44px]",
                                        "transition-colors",
                                        hasDetails && "hover:bg-secondary/50 cursor-pointer",
                                        !hasDetails && "cursor-default",
                                        stage.status === "running" && "bg-muted/30",
                                        stage.status === "completed" && "opacity-70",
                                        stage.status === "failed" && "bg-destructive/5"
                                    )}
                                >
                                    {/* Expand chevron - only show if has details */}
                                    {hasDetails ? (
                                        <ChevronDown
                                            className={cn(
                                                "w-3 h-3 text-muted-foreground transition-transform duration-200",
                                                !isStageExpanded && "-rotate-90"
                                            )}
                                        />
                                    ) : (
                                        <div className="w-3" />
                                    )}
                                    {getStageIcon(stage)}
                                    <span
                                        className={cn(
                                            "text-xs flex-1 text-left",
                                            stage.status === "running" && "text-foreground/80",
                                            stage.status === "completed" && "text-muted-foreground",
                                            stage.status === "failed" && "text-destructive",
                                            stage.status === "pending" && "text-muted-foreground/50"
                                        )}
                                    >
                                        {stage.label}
                                    </span>
                                    {/* Detail count badge */}
                                    {hasDetails && !isStageExpanded && (
                                        <span
                                            className="text-xs px-1.5 py-0.5 rounded bg-muted text-muted-foreground"
                                            aria-label={t("detailCount", { count: stage.progress.length })}
                                        >
                                            {stage.progress.length}
                                        </span>
                                    )}
                                </button>

                                {/* Progress details - only show when expanded */}
                                {hasDetails && isStageExpanded && (
                                    <div className="ml-6 md:ml-8 mt-1 space-y-0.5 border-l border-border pl-2.5 animate-in fade-in slide-in-from-top-1 duration-150">
                                        {stage.progress.map((detail) => (
                                            <div
                                                key={detail.key}
                                                className={cn(
                                                    "flex items-center gap-1.5 py-0.5 text-xs",
                                                    detail.type === "error" && "text-destructive",
                                                    detail.type === "info" && "text-muted-foreground/70",
                                                    detail.status === "running" && "text-muted-foreground",
                                                    detail.status === "completed" && "text-muted-foreground/60"
                                                )}
                                            >
                                                {getDetailIcon(detail)}
                                                <span className="flex-1 truncate">{detail.text}</span>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
