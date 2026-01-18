"use client";

import React, { useMemo, useState, useEffect } from "react";
import {
    Loader2,
    Check,
    AlertCircle,
    Search,
    Code2,
    PenTool,
    BarChart3,
    Link,
    X,
    Clock,
    ChevronRight,
    Globe,
    ExternalLink,
    PanelRightClose,
    PanelRight,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { useAgentProgressStore, type TimestampedEvent } from "@/lib/stores/agent-progress-store";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import type { AgentType, Source } from "@/lib/types";

// Agent icons for panel header
const AGENT_ICONS: Record<AgentType, React.ReactNode> = {
    chat: <Search className="w-5 h-5" />,
    research: <Search className="w-5 h-5" />,
    code: <Code2 className="w-5 h-5" />,
    writing: <PenTool className="w-5 h-5" />,
    data: <BarChart3 className="w-5 h-5" />,
};

// Stage group containing a stage and its child tools
interface StageGroup {
    stage: TimestampedEvent;
    stageIndex: number;
    tools: TimestampedEvent[];
    startTime: number;
    endTime?: number;
}

// Internal stages to hide from the UI (processing/routing phases)
const HIDDEN_STAGES = new Set(["thinking", "routing"]);

function groupEventsByStage(events: TimestampedEvent[], processingLabel: string = "Processing"): StageGroup[] {
    const groups: StageGroup[] = [];
    let currentGroup: StageGroup | null = null;
    // Track stage groups by name to update endTime when completion event arrives
    const stageGroupsByName: Record<string, StageGroup> = {};

    for (let i = 0; i < events.length; i++) {
        const event = events[i];

        if (event.type === "stage") {
            // Skip internal stages (thinking, routing)
            if (event.name && HIDDEN_STAGES.has(event.name)) {
                continue;
            }

            if (event.status === "running") {
                // Start a new group only for "running" stage events
                currentGroup = {
                    stage: event,
                    stageIndex: i,
                    tools: [],
                    startTime: event.timestamp,
                    endTime: event.endTimestamp,
                };
                groups.push(currentGroup);
                if (event.name) {
                    stageGroupsByName[event.name] = currentGroup;
                }
            } else if (event.status === "completed" || event.status === "failed") {
                // Update the existing group's endTime when we receive completion event
                const stageName = event.name;
                if (stageName && stageGroupsByName[stageName]) {
                    stageGroupsByName[stageName].endTime = event.endTimestamp || event.timestamp;
                    // Also update the stage event's endTimestamp for status calculation
                    stageGroupsByName[stageName].stage = {
                        ...stageGroupsByName[stageName].stage,
                        status: event.status,
                        endTimestamp: event.endTimestamp || event.timestamp,
                    };
                }
            }
        } else if (event.type === "tool_call") {
            // Add tool to current group or create an orphan group
            if (currentGroup) {
                currentGroup.tools.push(event);
            } else {
                // Create an implicit stage group for orphan tools
                const implicitGroup: StageGroup = {
                    stage: {
                        type: "stage",
                        name: "processing",
                        description: processingLabel,
                        status: "running",
                        timestamp: event.timestamp,
                    },
                    stageIndex: -1,
                    tools: [event],
                    startTime: event.timestamp,
                };
                groups.push(implicitGroup);
                currentGroup = implicitGroup;
            }
        }
        // Skip tool_result, source, etc. as they update existing items via store
    }

    return groups;
}

function formatToolName(name: string, defaultLabel: string = "Tool"): string {
    if (!name) return defaultLabel;
    return name
        .split("_")
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" ");
}

function formatDuration(startTime: Date): string {
    const elapsed = Math.floor((Date.now() - startTime.getTime()) / 1000);
    if (elapsed < 60) return `${elapsed}s`;
    const minutes = Math.floor(elapsed / 60);
    const seconds = elapsed % 60;
    return `${minutes}m ${seconds}s`;
}

function formatElapsedMs(startMs: number, endMs?: number): string {
    const duration = endMs ? endMs - startMs : Date.now() - startMs;
    const seconds = duration / 1000;
    if (seconds < 0.1) return "<0.1s";
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${minutes}m ${secs}s`;
}

// Known stage names that have translations (excludes hidden stages)
const KNOWN_STAGES = [
    "handoff", "chat", "analyze", "search", "tool", "write", "synthesize",
    "research", "plan", "generate", "execute", "summarize", "finalize",
    "outline", "data", "source", "code_result", "config", "search_tools",
    "collect", "report", "thinking", "routing"
];

// Get translated stage description based on stage name and status
function getTranslatedStageDescription(
    stage: TimestampedEvent,
    tStages: ReturnType<typeof useTranslations>
): string {
    const stageName = stage.name || "processing";
    const status = stage.status || "running";

    if (KNOWN_STAGES.includes(stageName)) {
        try {
            const key = `${stageName}.${status}` as Parameters<typeof tStages>[0];
            const translated = tStages(key);
            if (translated && !translated.includes(stageName)) {
                return translated;
            }
        } catch {
            // Translation not found, fall back
        }
    }
    // Fall back to raw description or formatted stage name
    return stage.description || stageName.charAt(0).toUpperCase() + stageName.slice(1);
}

// Live elapsed time component
function LiveDuration({ startMs, endMs }: { startMs: number; endMs?: number }) {
    const [, setTick] = useState(0);

    useEffect(() => {
        if (endMs) return; // No need to update if completed
        const interval = setInterval(() => setTick(t => t + 1), 100);
        return () => clearInterval(interval);
    }, [endMs]);

    return <span className="tabular-nums">{formatElapsedMs(startMs, endMs)}</span>;
}

// Tool item component with expandable args
function ToolItem({ tool, isStreaming }: { tool: TimestampedEvent; isStreaming: boolean }) {
    const tTools = useTranslations("chat.agent.tools");
    const tProgress = useTranslations("sidebar.progress");
    const [isExpanded, setIsExpanded] = useState(false);
    const toolName = tool.tool || "tool";
    const args = tool.args || {};
    const hasArgs = Object.keys(args).length > 0;
    const isSearch = toolName === "web_search" || toolName === "google_search" || toolName === "web";
    const query = (args as Record<string, unknown>).query as string | undefined;
    // Tool is only running if streaming is active AND no endTimestamp
    // When streaming ends, all tools show as completed
    const isRunning = isStreaming && !tool.endTimestamp;

    // Get translated tool name, fallback to formatted name
    const defaultToolLabel = tProgress("defaultTool");
    const getToolDisplayName = () => {
        if (isSearch && query) return query;
        // Known tool names from translations
        const toolTranslations: Record<string, string> = {
            web_search: tTools("web_search"),
            google_search: tTools("google_search"),
            web: tTools("web"),
            generate_image: tTools("generate_image"),
            analyze_image: tTools("analyze_image"),
            execute_code: tTools("execute_code"),
            sandbox_file: tTools("sandbox_file"),
            browser_use: tTools("browser_use"),
            browser_navigate: tTools("browser_navigate"),
        };
        return toolTranslations[toolName] || formatToolName(toolName, defaultToolLabel);
    };

    return (
        <div
            className={cn(
                "flex items-center gap-2.5 py-1.5 px-3 ml-6 rounded-md transition-colors",
                hasArgs && "cursor-pointer hover:bg-muted/40",
                isRunning && "bg-muted/20"
            )}
            onClick={() => hasArgs && setIsExpanded(!isExpanded)}
        >
            {/* Status indicator - minimal */}
            <div className="w-4 h-4 flex items-center justify-center flex-shrink-0">
                {isRunning ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground" />
                ) : (
                    <Check className="w-3.5 h-3.5 text-[hsl(var(--accent-success))]" />
                )}
            </div>

            {/* Tool name with inline icon */}
            <span className={cn(
                "text-sm flex-1 truncate",
                isRunning ? "text-foreground" : "text-muted-foreground"
            )}>
                {getToolDisplayName()}
            </span>

            {/* Duration */}
            <span className="text-xs text-muted-foreground/60 tabular-nums flex-shrink-0">
                <LiveDuration startMs={tool.timestamp} endMs={tool.endTimestamp} />
            </span>

            {/* Expand chevron - only if has args */}
            {hasArgs && (
                <ChevronRight className={cn(
                    "w-3.5 h-3.5 text-muted-foreground/40 transition-transform flex-shrink-0",
                    isExpanded && "rotate-90"
                )} />
            )}
        </div>
    );

    // Note: Removed expanded args section for cleaner visual - can be added back if needed
}

// Stage group component with collapsible tools
function StageGroupItem({ group, defaultExpanded, isStreaming }: { group: StageGroup; defaultExpanded: boolean; isStreaming: boolean }) {
    const tProgress = useTranslations("sidebar.progress");
    const tStages = useTranslations("chat.agent.stages");
    const [isExpanded, setIsExpanded] = useState(defaultExpanded);
    const { stage, tools } = group;
    const hasTools = tools.length > 0;

    const stageDescription = getTranslatedStageDescription(stage, tStages);

    const isFailed = stage.status === "failed";

    // A stage with tools is completed when ALL its tools have completed,
    // even if the backend hasn't sent a stage completion event yet
    const allToolsCompleted = hasTools && tools.every(t => t.endTimestamp);

    // A stage is running only if:
    // 1. Streaming is still active (task not completed)
    // 2. Stage status is "running" AND (no tools OR some tools still running)
    // When streaming ends, no stage should show as "running" anymore
    const isRunning = isStreaming && !isFailed && stage.status === "running" && (!hasTools || tools.some(t => !t.endTimestamp));

    // A stage is completed if:
    // 1. Stage status is "completed", OR
    // 2. Stage has an endTimestamp, OR
    // 3. Stage has tools and ALL tools have completed, OR
    // 4. Streaming has ended (task is complete) - all remaining stages are implicitly complete
    const isCompleted = !isFailed && !isRunning && (
        stage.status === "completed" ||
        stage.endTimestamp !== undefined ||
        allToolsCompleted ||
        !isStreaming
    );

    return (
        <div className="rounded-lg overflow-hidden">
            {/* Stage header */}
            <div
                className={cn(
                    "flex items-center gap-3 p-3 transition-colors",
                    hasTools && "cursor-pointer hover:bg-muted/30"
                )}
                onClick={() => hasTools && setIsExpanded(!isExpanded)}
            >
                {/* Status indicator - unified size */}
                <div className={cn(
                    "w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0",
                    isRunning && "bg-foreground text-background",
                    isCompleted && "bg-[hsl(var(--accent-success))/0.15]",
                    isFailed && "bg-destructive/15"
                )}>
                    {isRunning ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : isFailed ? (
                        <AlertCircle className="w-3.5 h-3.5 text-destructive" />
                    ) : (
                        <Check className="w-3.5 h-3.5 text-[hsl(var(--accent-success))]" />
                    )}
                </div>

                {/* Stage content */}
                <div className="flex-1 min-w-0">
                    <span className={cn(
                        "text-sm font-medium truncate block",
                        isRunning && "text-foreground",
                        isCompleted && "text-muted-foreground",
                        isFailed && "text-destructive"
                    )}>
                        {stageDescription}
                    </span>
                    {hasTools && (
                        <span className="text-xs text-muted-foreground/60">
                            {tProgress("toolCount", { count: tools.length })}
                        </span>
                    )}
                </div>

                {/* Duration */}
                <span className="text-xs text-muted-foreground/60 tabular-nums flex-shrink-0">
                    <LiveDuration startMs={group.startTime} endMs={group.endTime} />
                </span>

                {/* Expand chevron */}
                {hasTools && (
                    <ChevronRight className={cn(
                        "w-4 h-4 text-muted-foreground/40 transition-transform flex-shrink-0",
                        isExpanded && "rotate-90"
                    )} />
                )}
            </div>

            {/* Tool list - cleaner indent */}
            {isExpanded && hasTools && (
                <div className="pb-2 space-y-0.5">
                    {tools.map((tool, idx) => (
                        <ToolItem key={`${tool.tool}-${idx}`} tool={tool} isStreaming={isStreaming} />
                    ))}
                </div>
            )}
        </div>
    );
}

// Sources section component - matches stage group visual style
function SourcesSection({ sources, isExpanded: defaultExpanded }: { sources: Source[]; isExpanded?: boolean }) {
    const [isExpanded, setIsExpanded] = useState(defaultExpanded ?? true);
    const tProgress = useTranslations("sidebar.progress");

    if (sources.length === 0) return null;

    return (
        <div className="border-t border-border/50 pt-3 mt-2">
            {/* Header - matches StageGroupItem header style */}
            <div
                className="flex items-center gap-3 p-3 cursor-pointer hover:bg-muted/30 rounded-lg transition-colors"
                onClick={() => setIsExpanded(!isExpanded)}
            >
                {/* Icon container - matches stage status indicator size */}
                <div className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 bg-muted/50">
                    <Globe className="w-3.5 h-3.5 text-muted-foreground" />
                </div>

                {/* Label */}
                <span className="text-sm font-medium text-muted-foreground flex-1">
                    {tProgress("sourcesCount", { count: sources.length })}
                </span>

                {/* Expand chevron - matches stage chevron */}
                <ChevronRight className={cn(
                    "w-4 h-4 text-muted-foreground/40 transition-transform flex-shrink-0",
                    isExpanded && "rotate-90"
                )} />
            </div>

            {/* Source list */}
            {isExpanded && (
                <div className="space-y-0.5 pb-2">
                    {sources.map((source) => (
                        <a
                            key={source.id}
                            href={source.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="group flex items-center gap-2.5 py-1.5 px-3 ml-6 rounded-md hover:bg-muted/40 transition-colors"
                        >
                            <Link className="w-4 h-4 text-muted-foreground/60 shrink-0" />
                            <span className="text-sm text-muted-foreground truncate flex-1 group-hover:text-foreground transition-colors">
                                {source.title}
                            </span>
                            <ExternalLink className="w-3 h-3 text-muted-foreground/40 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
                        </a>
                    ))}
                </div>
            )}
        </div>
    );
}

export function AgentProgressPanel() {
    const t = useTranslations("agents");
    const tChat = useTranslations("chat.agent");
    const tProgress = useTranslations("sidebar.progress");
    const tStages = useTranslations("chat.agent.stages");
    const { activeProgress, isCompleted, isPanelOpen, closePanel, clearProgress } = useAgentProgressStore();
    const [isExpanded, setIsExpanded] = useState(true);

    const processingLabel = tProgress("processing");
    const stageGroups = useMemo(() => {
        if (!activeProgress) return [];
        return groupEventsByStage(activeProgress.events, processingLabel);
    }, [activeProgress, processingLabel]);

    const progressSummary = useMemo(() => {
        if (!activeProgress) return null;

        const { isStreaming: streaming } = activeProgress;

        // Helper to check if a stage is running (matches StageGroupItem logic)
        const isStageRunning = (g: StageGroup) => {
            if (g.stage.status === "failed") return false;
            const hasTools = g.tools.length > 0;
            // When streaming ends, no stage should show as "running" anymore
            return streaming && g.stage.status === "running" &&
                   (!hasTools || g.tools.some(t => !t.endTimestamp));
        };

        // Helper to check if a stage is completed (matches StageGroupItem logic)
        const isStageCompleted = (g: StageGroup) => {
            if (g.stage.status === "failed") return false;
            const hasTools = g.tools.length > 0;
            const allToolsCompleted = hasTools && g.tools.every(t => t.endTimestamp);
            const running = isStageRunning(g);
            return !running && (
                g.stage.status === "completed" ||
                g.stage.endTimestamp !== undefined ||
                allToolsCompleted ||
                !streaming
            );
        };

        const completedStages = stageGroups.filter(isStageCompleted).length;
        const runningStages = stageGroups.filter(isStageRunning).length;
        const totalTools = stageGroups.reduce((sum, g) => sum + g.tools.length, 0);
        const completedTools = stageGroups.reduce((sum, g) =>
            sum + g.tools.filter(t => t.endTimestamp).length, 0
        );
        const failedCount = stageGroups.filter(g => g.stage.status === "failed").length;

        return {
            completedStages,
            runningStages,
            totalStages: stageGroups.length,
            totalTools,
            completedTools,
            hasError: failedCount > 0,
        };
    }, [activeProgress, stageGroups]);

    if (!activeProgress || !isPanelOpen) return null;

    const { agentType, isStreaming, currentStage, startTime, sources } = activeProgress;
    const agentName = t(`${agentType}.name`);
    const agentIcon = AGENT_ICONS[agentType];

    const handleClose = () => {
        closePanel();
        if (isCompleted) {
            setTimeout(() => clearProgress(), 300);
        }
    };

    return (
        <>
            {/* Backdrop for mobile */}
            <div
                className={cn(
                    "fixed inset-0 bg-black/20 backdrop-blur-sm z-40 lg:hidden transition-opacity duration-300",
                    isPanelOpen ? "opacity-100" : "opacity-0 pointer-events-none"
                )}
                onClick={handleClose}
            />

            {/* Panel Container */}
            <div
                className={cn(
                    "fixed right-0 top-0 bottom-0 z-50 flex flex-col transition-all duration-300 ease-in-out",
                    "bg-background/95 backdrop-blur-md border-l border-border shadow-2xl",
                    isPanelOpen ? "translate-x-0" : "translate-x-full",
                    // Width changes based on expanded state
                    isExpanded
                        ? "w-full lg:w-[400px] xl:w-[450px]"
                        : "w-[280px] lg:w-[320px]"
                )}
            >
                {/* Header */}
                <div className="flex items-center justify-between px-4 h-14 border-b border-border/50 shrink-0">
                    <div className="flex items-center gap-3 min-w-0">
                        {/* Status indicator */}
                        <div className="relative flex-shrink-0">
                            {isStreaming ? (
                                <span className="flex items-center justify-center w-8 h-8 rounded-full bg-foreground text-background">
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                </span>
                            ) : progressSummary?.hasError ? (
                                <span className="flex items-center justify-center w-8 h-8 rounded-full bg-destructive text-white">
                                    <AlertCircle className="w-4 h-4" />
                                </span>
                            ) : (
                                <span className="flex items-center justify-center w-8 h-8 rounded-full bg-foreground text-background">
                                    <Check className="w-4 h-4" strokeWidth={3} />
                                </span>
                            )}
                        </div>

                        <div className="flex flex-col min-w-0">
                            <div className="flex items-center gap-2">
                                <span className="text-muted-foreground">{agentIcon}</span>
                                <h3 className="text-sm font-semibold truncate">{agentName}</h3>
                            </div>
                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                <Clock className="w-3 h-3" />
                                <span>{formatDuration(startTime)}</span>
                                {progressSummary && (
                                    <>
                                        <span className="text-border">|</span>
                                        <span>
                                            {tProgress("stageCount", { count: progressSummary.totalStages })}
                                            {progressSummary.totalTools > 0 && `, ${tProgress("toolCount", { count: progressSummary.totalTools })}`}
                                        </span>
                                    </>
                                )}
                            </div>
                        </div>
                    </div>

                    <div className="flex items-center gap-1 shrink-0">
                        {/* Expand/Collapse toggle */}
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setIsExpanded(!isExpanded)}
                            title={isExpanded ? tProgress("collapse") : tProgress("expand")}
                        >
                            {isExpanded ? (
                                <PanelRightClose className="w-4 h-4" />
                            ) : (
                                <PanelRight className="w-4 h-4" />
                            )}
                        </Button>
                        {/* Close button */}
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={handleClose}
                        >
                            <X className="w-4 h-4" />
                        </Button>
                    </div>
                </div>

                {/* Current Stage Banner */}
                {isStreaming && currentStage && !HIDDEN_STAGES.has(currentStage) && (
                    <div className="px-4 py-3 bg-muted/50 border-b border-border/30 flex items-center gap-3">
                        <Loader2 className="w-4 h-4 animate-spin text-foreground flex-shrink-0" />
                        <span className="text-sm font-medium truncate">
                            {KNOWN_STAGES.includes(currentStage)
                                ? tStages(`${currentStage}.running` as Parameters<typeof tStages>[0])
                                : currentStage}
                        </span>
                    </div>
                )}

                {/* Completion Banner */}
                {!isStreaming && (
                    <div className={cn(
                        "px-4 py-3 border-b border-border/30 flex items-center gap-3",
                        progressSummary?.hasError ? "bg-destructive/10" : "bg-[hsl(var(--accent-success))/0.1]"
                    )}>
                        {progressSummary?.hasError ? (
                            <>
                                <AlertCircle className="w-4 h-4 text-destructive flex-shrink-0" />
                                <span className="text-sm font-medium text-destructive">{tChat("completedWithErrors")}</span>
                            </>
                        ) : (
                            <>
                                <Check className="w-4 h-4 text-[hsl(var(--accent-success))] flex-shrink-0" />
                                <span className="text-sm font-medium text-[hsl(var(--accent-success))]">{tChat("completed")}</span>
                            </>
                        )}
                    </div>
                )}

                {/* Stage Groups Timeline - only show when expanded */}
                {isExpanded ? (
                    <ScrollArea className="flex-1">
                        <div className="p-4 space-y-2">
                            {stageGroups.length === 0 && isStreaming && (
                                <div className="flex items-center justify-center py-8">
                                    <div className="flex items-center gap-3 text-muted-foreground">
                                        <Loader2 className="w-5 h-5 animate-spin" />
                                        <span className="text-sm">{tChat("thinking")}</span>
                                    </div>
                                </div>
                            )}

                            {stageGroups.map((group, index) => (
                                <StageGroupItem
                                    key={`stage-${index}`}
                                    group={group}
                                    defaultExpanded={index === stageGroups.length - 1 || group.stage.status === "running"}
                                    isStreaming={isStreaming}
                                />
                            ))}

                            {/* Sources Section */}
                            {sources.length > 0 && (
                                <SourcesSection sources={sources} isExpanded={!isStreaming} />
                            )}
                        </div>
                    </ScrollArea>
                ) : (
                    /* Collapsed view - show simplified progress list */
                    <ScrollArea className="flex-1">
                        <div className="p-3 space-y-1.5">
                            {stageGroups.length === 0 && isStreaming && (
                                <div className="flex items-center gap-2 text-muted-foreground py-2">
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                    <span className="text-sm">{tChat("thinking")}</span>
                                </div>
                            )}

                            {stageGroups.map((group, index) => {
                                const hasTools = group.tools.length > 0;
                                const allToolsCompleted = hasTools && group.tools.every(t => t.endTimestamp);
                                // When streaming ends, no stage should show as "running" anymore
                                const isStageRunning = isStreaming && group.stage.status === "running" && (!hasTools || group.tools.some(t => !t.endTimestamp));
                                const isStageCompleted = !isStageRunning && (group.stage.status === "completed" || group.stage.endTimestamp !== undefined || allToolsCompleted || !isStreaming);
                                const isStageFailed = group.stage.status === "failed";

                                const stageDescription = getTranslatedStageDescription(group.stage, tStages);

                                return (
                                    <div
                                        key={`stage-collapsed-${index}`}
                                        className={cn(
                                            "flex items-center gap-2 px-2 py-1.5 rounded-md text-sm",
                                            isStageRunning && "bg-muted/50",
                                            isStageCompleted && "text-muted-foreground",
                                            isStageFailed && "text-destructive"
                                        )}
                                    >
                                        {isStageRunning ? (
                                            <Loader2 className="w-3.5 h-3.5 animate-spin flex-shrink-0" />
                                        ) : isStageCompleted ? (
                                            <Check className="w-3.5 h-3.5 text-[hsl(var(--accent-success))] flex-shrink-0" />
                                        ) : isStageFailed ? (
                                            <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
                                        ) : (
                                            <div className="w-3.5 h-3.5 flex-shrink-0" />
                                        )}
                                        <span className="truncate flex-1">{stageDescription}</span>
                                        {hasTools && (
                                            <span className="text-xs text-muted-foreground/70 flex-shrink-0">
                                                {group.tools.filter(t => t.endTimestamp).length}/{group.tools.length}
                                            </span>
                                        )}
                                    </div>
                                );
                            })}

                            {/* Sources count in collapsed view */}
                            {sources.length > 0 && (
                                <div className="flex items-center gap-2 px-2 py-1.5 text-sm text-muted-foreground">
                                    <Globe className="w-3.5 h-3.5 flex-shrink-0" />
                                    <span>{tProgress("sourcesCount", { count: sources.length })}</span>
                                </div>
                            )}
                        </div>
                    </ScrollArea>
                )}

                {/* Footer with summary */}
                {progressSummary && progressSummary.totalStages > 0 && (
                    <div className="px-4 py-3 border-t border-border/50 bg-muted/30">
                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                            <span>
                                {tProgress("stagesProgress", { completed: progressSummary.completedStages, total: progressSummary.totalStages })}
                                {progressSummary.totalTools > 0 && (
                                    <>, {tProgress("toolsProgress", { completed: progressSummary.completedTools, total: progressSummary.totalTools })}</>
                                )}
                            </span>
                            {isStreaming && progressSummary.runningStages > 0 && (
                                <span className="flex items-center gap-1">
                                    <Loader2 className="w-3 h-3 animate-spin" />
                                    {tProgress("running", { count: progressSummary.runningStages })}
                                </span>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </>
    );
}
