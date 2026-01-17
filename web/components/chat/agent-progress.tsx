"use client";

import React, { useMemo, useState, useEffect, memo } from "react";
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
    ImageIcon,
    Eye,
    ArrowRight,
    Share2,
    Link,
    Terminal,
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
    type: "info" | "tool" | "search" | "error" | "image_generate" | "image_analyze" | "source" | "code";
    status?: "running" | "completed" | "failed";
    toolCallId?: string; // Unique ID for matching tool_call with tool_result
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
    routing: <ArrowRight className="w-3.5 h-3.5" />,
    handoff: <Share2 className="w-3.5 h-3.5" />,
    chat: <Brain className="w-3.5 h-3.5" />,
    search: <Search className="w-3.5 h-3.5" />,
    tool: <Wrench className="w-3.5 h-3.5" />,
    analyze: <FileText className="w-3.5 h-3.5" />,
    synthesize: <FileText className="w-3.5 h-3.5" />,
    write: <PenTool className="w-3.5 h-3.5" />,
    generate: <Code className="w-3.5 h-3.5" />,
    execute: <Code className="w-3.5 h-3.5" />,
    code_result: <Terminal className="w-3.5 h-3.5" />,
    plan: <Brain className="w-3.5 h-3.5" />,
    summarize: <FileText className="w-3.5 h-3.5" />,
    finalize: <Check className="w-3.5 h-3.5" />,
    outline: <FileText className="w-3.5 h-3.5" />,
    data: <BarChart3 className="w-3.5 h-3.5" />,
    image_generate: <ImageIcon className="w-3.5 h-3.5" />,
    image_analyze: <Eye className="w-3.5 h-3.5" />,
    source: <Link className="w-3.5 h-3.5" />,
};

export const AgentProgress = memo(function AgentProgress({ status, agentEvents, isStreaming, className }: AgentProgressProps) {
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

        // Known tools that have translations
        const KNOWN_TOOLS = new Set([
            "web_search", "google_search", "web",
            "generate_image", "analyze_image",
            "execute_code", "sandbox_file",
            "browser_use", "browser_navigate",
        ]);

        const getToolLabel = (toolName: string): string => {
            // Return default if toolName is empty or invalid
            if (!toolName || typeof toolName !== "string" || toolName.trim() === "") {
                return "Tool";
            }

            // Handle handoff tools - format nicely without translation
            if (toolName.startsWith("handoff_to_")) {
                const target = toolName.replace("handoff_to_", "");
                return `Handoff → ${target.charAt(0).toUpperCase() + target.slice(1)}`;
            }

            // Only try translation for known tools to avoid errors
            if (KNOWN_TOOLS.has(toolName)) {
                try {
                    const key = `tools.${toolName}`;
                    const translated = t(key as any);
                    if (translated && translated !== key) {
                        return translated;
                    }
                } catch {
                    // fallback below
                }
            }

            // Format unknown tools nicely: "my_tool" -> "My Tool"
            return toolName
                .split("_")
                .map(word => word.charAt(0).toUpperCase() + word.slice(1))
                .join(" ");
        };

        // Stages to skip when completed (internal routing/thinking stages)
        const SKIP_COMPLETED_STAGES = new Set(["thinking", "routing"]);

        // Helper to auto-complete thinking stage when real work starts
        const autoCompleteThinking = () => {
            const thinkingKey = "stage:thinking";
            if (stageMap.has(thinkingKey)) {
                const thinking = stageMap.get(thinkingKey)!;
                if (thinking.status === "running") {
                    // Remove thinking stage when real work starts
                    const idx = stages.indexOf(thinking);
                    if (idx !== -1) {
                        stages.splice(idx, 1);
                    }
                    stageMap.delete(thinkingKey);
                }
            }
        };

        for (const event of agentEvents || []) {
            if (event.type === "stage") {
                const stepName = String(event.name || event.data?.name || "");
                const description = String(event.description || event.data?.description || "");
                const stepStatus = normalizeStatus(event.status || event.data?.status);
                const key = `stage:${stepName || "default"}`;

                // Skip internal stages only when completed (allow running state to show)
                if (SKIP_COMPLETED_STAGES.has(stepName) && stepStatus === "completed") {
                    // If we have an existing running stage, mark it for removal
                    if (stageMap.has(key)) {
                        const existing = stageMap.get(key)!;
                        // Remove from stages array
                        const idx = stages.indexOf(existing);
                        if (idx !== -1) {
                            stages.splice(idx, 1);
                        }
                        stageMap.delete(key);
                    }
                    continue;
                }

                // Auto-complete thinking stage when a real stage starts
                if (!SKIP_COMPLETED_STAGES.has(stepName) && stepStatus === "running") {
                    autoCompleteThinking();
                }

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
                // Note: Don't auto-complete thinking here - wait for a real stage to replace it

                const toolName = event.tool || event.data?.tool || "";
                const toolCallId = event.id || event.data?.id || `${toolName}:${Date.now()}`;
                const args = event.args || event.data?.args || {};
                const query = args.query || "";
                const prompt = args.prompt || "";
                const isSearch = toolName === "web_search" || toolName === "google_search" || toolName === "web";
                const isImageGenerate = toolName === "generate_image";
                const isImageAnalyze = toolName === "analyze_image";

                // Determine detail type and text
                let detailType: ProgressDetail["type"] = "tool";
                let detailText = t("executing", { tool: getToolLabel(toolName) });

                if (isSearch) {
                    detailType = "search";
                    detailText = query
                        ? t("searchingQuery", { query: truncateText(query) })
                        : t("searching");
                } else if (isImageGenerate) {
                    detailType = "image_generate";
                    detailText = prompt
                        ? t("generatingImage", { prompt: truncateText(prompt, 40) })
                        : t("generatingImageDefault");
                } else if (isImageAnalyze) {
                    detailType = "image_analyze";
                    detailText = prompt
                        ? t("analyzingImage", { prompt: truncateText(prompt, 40) })
                        : t("analyzingImageDefault");
                }

                const detail: ProgressDetail = {
                    key: `tool:${toolName}:${Date.now()}:${detailCounter++}`,
                    text: detailText,
                    type: detailType,
                    status: "running",
                    toolCallId, // Track tool call ID for matching results
                };

                if (currentStage) {
                    currentStage.progress.push(detail);
                } else {
                    // Create implicit stage for orphan tools
                    let implicitLabel = t("processing");
                    if (isSearch) implicitLabel = t("stages.search.running");
                    else if (isImageGenerate) implicitLabel = t("generatingImageDefault");
                    else if (isImageAnalyze) implicitLabel = t("analyzingImageDefault");

                    const implicitStage: StageItem = {
                        key: `stage:tool:${Date.now()}:${detailCounter++}`,
                        name: isImageGenerate ? "image_generate" : isImageAnalyze ? "image_analyze" : "tool",
                        label: implicitLabel,
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
                const toolCallId = event.id || event.data?.id;

                // First try to match by tool call ID (more precise)
                // Then fallback to matching by tool name (backward compatible)
                if (currentStage) {
                    let matched = false;

                    // Try exact ID match first
                    if (toolCallId) {
                        for (let i = currentStage.progress.length - 1; i >= 0; i--) {
                            const item = currentStage.progress[i];
                            if (item.toolCallId && item.toolCallId === toolCallId && item.status === "running") {
                                item.status = "completed";
                                matched = true;
                                break;
                            }
                        }
                    }

                    // Fallback to tool name match if ID match failed
                    if (!matched) {
                        for (let i = currentStage.progress.length - 1; i >= 0; i--) {
                            const item = currentStage.progress[i];
                            if (item.status === "running" && item.key.includes(`tool:${toolName}`)) {
                                item.status = "completed";
                                break;
                            }
                        }
                    }
                }
            } else if (event.type === "routing") {
                // Skip routing events - internal detail not shown to users
                continue;
            } else if (event.type === "handoff") {
                // Auto-complete thinking stage when handoff occurs
                autoCompleteThinking();

                // Handle agent handoff events
                const source = event.source || "";
                const target = event.target || "";
                const task = event.task || "";

                const handoffStage: StageItem = {
                    key: `stage:handoff:${Date.now()}:${detailCounter++}`,
                    name: "handoff",
                    label: t("handoffTo", { target }),
                    status: "running",
                    type: "stage",
                    progress: [
                        {
                            key: `detail:handoff:${Date.now()}:${detailCounter++}`,
                            text: task
                                ? `${source} → ${target}: ${truncateText(task)}`
                                : `${source} → ${target}`,
                            type: "info",
                            status: "running",
                        },
                    ],
                    timestamp: event.timestamp || Date.now(),
                };

                stages.push(handoffStage);
                stageMap.set(handoffStage.key, handoffStage);
                currentStage = handoffStage;
            } else if (event.type === "source") {
                // Handle source events from search results
                const title = event.title || event.data?.title || "";
                const url = event.url || event.data?.url || "";

                const sourceDetail: ProgressDetail = {
                    key: `source:${Date.now()}:${detailCounter++}`,
                    text: title || url || t("sourceFound"),
                    type: "source",
                    status: "completed",
                };

                if (currentStage) {
                    currentStage.progress.push(sourceDetail);
                } else {
                    // Create a sources stage if none exists
                    const sourcesKey = "stage:sources";
                    if (stageMap.has(sourcesKey)) {
                        stageMap.get(sourcesKey)!.progress.push(sourceDetail);
                    } else {
                        const sourcesStage: StageItem = {
                            key: sourcesKey,
                            name: "source",
                            label: t("stages.search.running"),
                            status: "running",
                            type: "stage",
                            progress: [sourceDetail],
                            timestamp: event.timestamp || Date.now(),
                        };
                        stages.push(sourcesStage);
                        stageMap.set(sourcesKey, sourcesStage);
                        currentStage = sourcesStage;
                    }
                }
            } else if (event.type === "code_result") {
                // Handle code execution result events
                const output = event.output || "";
                const exitCode = event.exit_code;
                const error = event.error || "";
                const isSuccess = exitCode === 0 || (!error && exitCode === undefined);

                const codeDetail: ProgressDetail = {
                    key: `code:${Date.now()}:${detailCounter++}`,
                    text: isSuccess
                        ? t("codeExecuted")
                        : t("codeError", { error: truncateText(error || output, 40) }),
                    type: isSuccess ? "code" : "error",
                    status: isSuccess ? "completed" : "failed",
                };

                if (currentStage) {
                    currentStage.progress.push(codeDetail);
                } else {
                    // Create an execution stage
                    const execStage: StageItem = {
                        key: `stage:execute:${Date.now()}:${detailCounter++}`,
                        name: "execute",
                        label: isSuccess ? t("stages.execute.completed") : t("stages.execute.failed"),
                        status: isSuccess ? "completed" : "failed",
                        type: "stage",
                        progress: [codeDetail],
                        timestamp: event.timestamp || Date.now(),
                    };
                    stages.push(execStage);
                    stageMap.set(execStage.key, execStage);
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [agentEvents]);

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
        if (detail.type === "image_generate") {
            if (detail.status === "running") return <Loader2 className="w-3 h-3 animate-spin text-foreground" />;
            if (detail.status === "completed") return <Check className="w-3 h-3 text-foreground" />;
            return <ImageIcon className="w-3 h-3 text-muted-foreground" />;
        }
        if (detail.type === "image_analyze") {
            if (detail.status === "running") return <Loader2 className="w-3 h-3 animate-spin text-foreground" />;
            if (detail.status === "completed") return <Check className="w-3 h-3 text-foreground" />;
            return <Eye className="w-3 h-3 text-muted-foreground" />;
        }
        if (detail.type === "source") {
            if (detail.status === "completed") return <Link className="w-3 h-3 text-foreground" />;
            return <Link className="w-3 h-3 text-muted-foreground" />;
        }
        if (detail.type === "code") {
            if (detail.status === "running") return <Loader2 className="w-3 h-3 animate-spin text-foreground" />;
            if (detail.status === "completed") return <Check className="w-3 h-3 text-foreground" />;
            if (detail.status === "failed") return <AlertCircle className="w-3 h-3 text-destructive" />;
            return <Terminal className="w-3 h-3 text-muted-foreground" />;
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
                    (isStreaming || activityState.hasRunning) && "ring-1 ring-foreground/50"
                )}
                aria-label={isCollapsed ? t("expandStage") : t("collapseStage")}
                aria-expanded={!isCollapsed}
            >
                <div className="flex items-center gap-3">
                    {(isStreaming || activityState.hasRunning) ? (
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
                        {(isStreaming || activityState.hasRunning)
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
});
