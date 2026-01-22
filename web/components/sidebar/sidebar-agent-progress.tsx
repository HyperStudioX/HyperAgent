"use client";

import React, { useMemo, useState, useEffect } from "react";
import {
    Loader2,
    Check,
    AlertCircle,
    Link,
    X,
    ChevronRight,
    Globe,
    PanelRightClose,
    PanelRight,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { useAgentProgressStore, type TimestampedEvent } from "@/lib/stores/agent-progress-store";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { ComputerViewer } from "@/components/ui/computer-viewer";
import type { Source } from "@/lib/types";

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

function groupEventsByStage(events: TimestampedEvent[], processingLabel: string): StageGroup[] {
    const groups: StageGroup[] = [];
    let currentGroup: StageGroup | null = null;
    // Track stage groups by name to update endTime when completion event arrives
    const stageGroupsByName: Record<string, StageGroup> = {};
    // Track seen tool IDs to prevent duplicates
    const seenToolIds = new Set<string>();

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
            // Generate unique key for deduplication (use id if available, otherwise tool+timestamp)
            const toolKey = event.id || `${event.tool || event.name}-${event.timestamp}`;

            // Skip if we've already seen this tool call
            if (seenToolIds.has(toolKey)) {
                continue;
            }
            seenToolIds.add(toolKey);

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
    "collect", "report", "thinking", "routing", "refine", "present",
    "analyze_image", "generate_image",
    // Browser action stages
    "browser_launch", "browser_navigate", "browser_click", "browser_type",
    "browser_screenshot", "browser_scroll", "browser_key", "browser_computer"
];

// Get translated stage description based on stage name, status, and agent type
function getTranslatedStageDescription(
    stage: TimestampedEvent,
    tStages: ReturnType<typeof useTranslations>,
    agentType?: string
): string {
    const stageName = stage.name || "processing";
    const status = stage.status || "running";

    // Handle agent-specific stage overrides for context-aware translations
    if (agentType === "image") {
        // Image agent uses generic stage names - try agent-specific translation first
        if (stageName === "analyze") {
            try {
                const key = `analyze_image.${status}` as Parameters<typeof tStages>[0];
                const translated = tStages(key);
                // Check if translation exists and is valid (not empty, not the key itself)
                if (translated && translated.trim() && translated !== key && !translated.includes("analyze_image")) {
                    return translated;
                }
            } catch {
                // Fall through to generic translation
            }
        }
        if (stageName === "generate") {
            try {
                const key = `generate_image.${status}` as Parameters<typeof tStages>[0];
                const translated = tStages(key);
                if (translated && translated.trim() && translated !== key && !translated.includes("generate_image")) {
                    return translated;
                }
            } catch {
                // Fall through to generic translation
            }
        }
    }

    // For known stages, always prioritize translation lookup over backend description
    // This ensures i18n support even if backend sends untranslated descriptions
    if (KNOWN_STAGES.includes(stageName)) {
        try {
            const key = `${stageName}.${status}` as Parameters<typeof tStages>[0];
            const translated = tStages(key);
            // Use translation if it exists and is valid
            // next-intl returns the key if translation is missing, so check if it's different
            // Also check it's not empty and doesn't look like a missing translation key
            if (
                translated &&
                translated.trim() &&
                translated !== key &&
                !translated.startsWith("chat.agent.stages") &&
                translated.length > 0
            ) {
                return translated;
            }
        } catch (e) {
            // Translation not found, will fall back to description or formatted name
            if (process.env.NODE_ENV === "development") {
                console.warn(`[getTranslatedStageDescription] Translation not found for ${stageName}.${status}:`, e);
            }
        }
    }
    
    // Fall back to stage description if provided (e.g., "processing" from sidebar.progress)
    // Only use this for unknown stages or when translation lookup fails
    if (stage.description) {
        return stage.description;
    }
    
    // Final fallback: formatted stage name (for i18n) instead of hardcoded descriptions
    // This ensures we don't show untranslated English strings from backend
    const formattedName = stageName.charAt(0).toUpperCase() + stageName.slice(1).replace(/_/g, " ");
    return formattedName;
}

// Live elapsed time component - updates every second for minimal visual noise
function LiveDuration({ startMs, endMs }: { startMs: number; endMs?: number }) {
    const [, setTick] = useState(0);

    useEffect(() => {
        if (endMs) return; // No need to update if completed
        const interval = setInterval(() => setTick(t => t + 1), 1000);
        return () => clearInterval(interval);
    }, [endMs]);

    return <span className="tabular-nums">{formatElapsedMs(startMs, endMs)}</span>;
}

// Tool item component - minimal inline design
function ToolItem({ tool, isStreaming }: { tool: TimestampedEvent; isStreaming: boolean }) {
    const tTools = useTranslations("chat.agent.tools");
    // Tool name can come from `tool` field or `name` field depending on backend
    const toolName = tool.tool || tool.name || "tool";
    const args = tool.args || {};
    const isSearch = toolName === "web_search" || toolName === "google_search" || toolName === "web";
    const query = (args as Record<string, unknown>).query as string | undefined;

    // Debug logging for tool name resolution
    if (process.env.NODE_ENV === "development") {
        console.log("[ToolItem]", {
            id: tool.id,
            toolField: tool.tool,
            nameField: tool.name,
            resolvedName: toolName,
            timestamp: tool.timestamp,
        });
    }

    // Determine tool status
    const isPending = tool.status === "pending" || (!tool.status && !tool.endTimestamp && isStreaming);
    const isRunning = tool.status === "running" || (isStreaming && !tool.endTimestamp && !isPending);
    const isFailed = tool.status === "failed";
    const isCompleted = tool.status === "completed" || tool.endTimestamp !== undefined || !isStreaming;

    const getToolDisplayName = () => {
        if (isSearch && query) return query;
        // Explicit mapping for known tools to ensure correct translation lookup
        const toolKey = toolName.toLowerCase();
        switch (toolKey) {
            case "web_search":
                return tTools("web_search");
            case "google_search":
                return tTools("google_search");
            case "web":
                return tTools("web");
            case "generate_image":
                return tTools("generate_image");
            case "analyze_image":
                return tTools("analyze_image");
            case "execute_code":
                return tTools("execute_code");
            case "sandbox_file":
                return tTools("sandbox_file");
            case "browser_use":
                return tTools("browser_use");
            case "browser_navigate":
                return tTools("browser_navigate");
            case "browser_screenshot":
                return tTools("browser_screenshot");
            case "browser_click":
                return tTools("browser_click");
            case "browser_type":
                return tTools("browser_type");
            case "browser_press_key":
                return tTools("browser_press_key");
            case "browser_scroll":
                return tTools("browser_scroll");
            case "browser_get_stream_url":
                return tTools("browser_get_stream_url");
            default:
                return tTools("default");
        }
    };

    const toolId = tool.id || `${toolName}-${tool.timestamp}`;

    return (
        <div
            className="flex items-center gap-2 py-1 pl-5 text-sm"
            data-tool-id={toolId}
            data-tool-name={toolName}
            data-tool-status={isPending ? "pending" : isRunning ? "running" : isFailed ? "failed" : "completed"}
        >
            {/* Status indicator */}
            <div className="w-4 h-4 flex items-center justify-center flex-shrink-0">
                {isPending ? (
                    <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground/20" />
                ) : isRunning ? (
                    <div className="w-2 h-2 rounded-full bg-foreground animate-pulse" />
                ) : isFailed ? (
                    <div className="w-1.5 h-1.5 rounded-full bg-destructive" />
                ) : (
                    <Check className="w-3.5 h-3.5 text-muted-foreground" />
                )}
            </div>

            <span className={cn(
                "flex-1 truncate",
                isPending && "text-muted-foreground/50",
                isRunning && "text-muted-foreground",
                isCompleted && !isFailed && "text-muted-foreground/70",
                isFailed && "text-destructive/80"
            )}>
                {getToolDisplayName()}
            </span>

            <span className="text-xs text-muted-foreground/50 tabular-nums">
                <LiveDuration startMs={tool.timestamp} endMs={tool.endTimestamp} />
            </span>
        </div>
    );
}

// Stage group component - clean and minimal
function StageGroupItem({ group, defaultExpanded, isStreaming, agentType }: { group: StageGroup; defaultExpanded: boolean; isStreaming: boolean; agentType?: string }) {
    const tStages = useTranslations("chat.agent.stages");
    const [isExpanded, setIsExpanded] = useState(defaultExpanded);
    const { stage, tools } = group;
    const hasTools = tools.length > 0;

    const stageDescription = getTranslatedStageDescription(stage, tStages, agentType);

    const isFailed = stage.status === "failed";
    const isPending = stage.status === "pending";
    const allToolsCompleted = hasTools && tools.every(t => t.endTimestamp || t.status === "completed");
    const isRunning = isStreaming && !isFailed && !isPending && stage.status === "running" &&
                      (!hasTools || tools.some(t => !t.endTimestamp && t.status !== "completed"));
    const isCompleted = !isFailed && !isRunning && !isPending && (
        stage.status === "completed" ||
        stage.endTimestamp !== undefined ||
        allToolsCompleted ||
        !isStreaming
    );

    const stageName = stage.name || "processing";
    const stageStatus = isPending ? "pending" : isRunning ? "running" : isFailed ? "failed" : "completed";

    return (
        <div
            data-stage-name={stageName}
            data-stage-status={stageStatus}
            data-stage-index={group.stageIndex}
            data-tools-count={tools.length}
        >
            {/* Stage row - single line */}
            <div
                className={cn(
                    "flex items-center gap-2 py-1.5 px-2 rounded-md transition-colors",
                    hasTools && "cursor-pointer hover:bg-secondary/50"
                )}
                onClick={() => hasTools && setIsExpanded(!isExpanded)}
            >
                {/* Status indicator */}
                <div className="w-5 h-5 flex items-center justify-center flex-shrink-0">
                    {isPending ? (
                        <div className="w-2 h-2 rounded-full bg-muted-foreground/20" />
                    ) : isRunning ? (
                        <div className="w-2.5 h-2.5 rounded-full bg-foreground animate-pulse" />
                    ) : isFailed ? (
                        <div className="w-2 h-2 rounded-full bg-destructive" />
                    ) : (
                        <Check className="w-4 h-4 text-muted-foreground" />
                    )}
                </div>

                {/* Stage name */}
                <span className={cn(
                    "text-sm flex-1 truncate",
                    isPending && "text-muted-foreground/50",
                    isRunning && "text-foreground font-medium",
                    isCompleted && "text-muted-foreground",
                    isFailed && "text-destructive"
                )}>
                    {stageDescription}
                </span>

                {/* Duration */}
                <span className="text-xs text-muted-foreground/50 tabular-nums">
                    <LiveDuration startMs={group.startTime} endMs={group.endTime} />
                </span>

                {/* Chevron for expandable */}
                {hasTools && (
                    <ChevronRight className={cn(
                        "w-3.5 h-3.5 text-muted-foreground/40 transition-transform",
                        isExpanded && "rotate-90"
                    )} />
                )}
            </div>

            {/* Tools list */}
            {isExpanded && hasTools && (
                <div className="mt-0.5 mb-1">
                    {tools.map((tool) => (
                        <ToolItem key={tool.id || `${tool.tool || tool.name}-${tool.timestamp}`} tool={tool} isStreaming={isStreaming} />
                    ))}
                </div>
            )}
        </div>
    );
}

// Sources section - minimal design
function SourcesSection({ sources, isExpanded: defaultExpanded }: { sources: Source[]; isExpanded?: boolean }) {
    const [isExpanded, setIsExpanded] = useState(defaultExpanded ?? true);
    const tProgress = useTranslations("sidebar.progress");

    if (sources.length === 0) return null;

    return (
        <div className="border-t border-border/30 pt-2 mt-2">
            <div
                className="flex items-center gap-2 py-1.5 px-2 rounded-md cursor-pointer hover:bg-secondary/50 transition-colors"
                onClick={() => setIsExpanded(!isExpanded)}
            >
                <Globe className="w-4 h-4 text-muted-foreground/60" />
                <span className="text-sm text-muted-foreground flex-1">
                    {tProgress("sourcesCount", { count: sources.length })}
                </span>
                <ChevronRight className={cn(
                    "w-3.5 h-3.5 text-muted-foreground/40 transition-transform",
                    isExpanded && "rotate-90"
                )} />
            </div>

            {isExpanded && (
                <div className="mt-0.5">
                    {sources.map((source) => (
                        <a
                            key={source.id}
                            href={source.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="group flex items-center gap-2 py-1 pl-5 text-sm hover:bg-secondary/30 rounded-md transition-colors"
                        >
                            <Link className="w-3 h-3 text-muted-foreground/50 shrink-0" />
                            <span className="text-muted-foreground/70 truncate flex-1 group-hover:text-foreground">
                                {source.title}
                            </span>
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
    const {
        activeProgress,
        isCompleted,
        isPanelOpen,
        closePanel,
        clearProgress,
        showBrowserStream,
        setShowBrowserStream,
        setBrowserStream,
    } = useAgentProgressStore();
    const [isExpanded, setIsExpanded] = useState(true);

    const processingLabel = tProgress("processing");
    const stageGroups = useMemo(() => {
        if (!activeProgress) return [];
        return groupEventsByStage(activeProgress.events, processingLabel);
    }, [activeProgress, processingLabel]);

    const progressSummary = useMemo(() => {
        if (!activeProgress) return null;

        const { isStreaming: streaming } = activeProgress;

        // Helper to check if a stage is pending (matches StageGroupItem logic)
        const isStagePending = (g: StageGroup) => {
            return g.stage.status === "pending";
        };

        // Helper to check if a stage is running (matches StageGroupItem logic)
        const isStageRunning = (g: StageGroup) => {
            if (g.stage.status === "failed" || g.stage.status === "pending") return false;
            const hasTools = g.tools.length > 0;
            // When streaming ends, no stage should show as "running" anymore
            return streaming && g.stage.status === "running" &&
                   (!hasTools || g.tools.some(t => !t.endTimestamp && t.status !== "completed"));
        };

        // Helper to check if a stage is completed (matches StageGroupItem logic)
        const isStageCompleted = (g: StageGroup) => {
            if (g.stage.status === "failed" || g.stage.status === "pending") return false;
            const hasTools = g.tools.length > 0;
            const allToolsCompleted = hasTools && g.tools.every(t => t.endTimestamp || t.status === "completed");
            const running = isStageRunning(g);
            return !running && (
                g.stage.status === "completed" ||
                g.stage.endTimestamp !== undefined ||
                allToolsCompleted ||
                !streaming
            );
        };

        const pendingStages = stageGroups.filter(isStagePending).length;
        const completedStages = stageGroups.filter(isStageCompleted).length;
        const runningStages = stageGroups.filter(isStageRunning).length;
        const totalTools = stageGroups.reduce((sum, g) => sum + g.tools.length, 0);
        const completedTools = stageGroups.reduce((sum, g) =>
            sum + g.tools.filter(t => t.endTimestamp || t.status === "completed").length, 0
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
                    "bg-background border-l border-border",
                    isPanelOpen ? "translate-x-0" : "translate-x-full",
                    // Wider panel when browser stream is active for better viewing (640px + padding)
                    activeProgress?.browserStream
                        ? "w-full lg:w-[680px]"
                        : isExpanded
                            ? "w-full lg:w-[340px]"
                            : "w-[260px]"
                )}
            >
                {/* Header - minimal */}
                <div className="flex items-center justify-between px-3 h-12 border-b border-border/50 shrink-0">
                    <div className="flex items-center gap-2 min-w-0">
                        {/* Simple status */}
                        {isStreaming ? (
                            <Loader2 className="w-4 h-4 animate-spin text-foreground flex-shrink-0" />
                        ) : progressSummary?.hasError ? (
                            <AlertCircle className="w-4 h-4 text-destructive flex-shrink-0" />
                        ) : (
                            <Check className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                        )}
                        <span className="text-sm font-medium truncate">{agentName}</span>
                        <span className="text-xs text-muted-foreground/60 tabular-nums">{formatDuration(startTime)}</span>
                    </div>

                    <div className="flex items-center shrink-0">
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => setIsExpanded(!isExpanded)}
                        >
                            {isExpanded ? (
                                <PanelRightClose className="w-4 h-4" />
                            ) : (
                                <PanelRight className="w-4 h-4" />
                            )}
                        </Button>
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={handleClose}
                        >
                            <X className="w-4 h-4" />
                        </Button>
                    </div>
                </div>

                {/* Current status - inline, not banner */}
                {isStreaming && currentStage && !HIDDEN_STAGES.has(currentStage) && (
                    <div className="px-3 py-2 text-sm text-muted-foreground border-b border-border/30 flex items-center gap-2">
                        <Loader2 className="w-3.5 h-3.5 animate-spin flex-shrink-0" />
                        <span className="truncate">
                            {KNOWN_STAGES.includes(currentStage)
                                ? tStages(`${currentStage}.running` as Parameters<typeof tStages>[0])
                                : currentStage}
                        </span>
                    </div>
                )}

                {/* Completion - subtle */}
                {!isStreaming && (
                    <div className={cn(
                        "px-3 py-2 text-sm border-b border-border/30 flex items-center gap-2",
                        progressSummary?.hasError ? "text-destructive" : "text-muted-foreground"
                    )}>
                        {progressSummary?.hasError ? (
                            <>
                                <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
                                <span>{tChat("completedWithErrors")}</span>
                            </>
                        ) : (
                            <>
                                <Check className="w-3.5 h-3.5 flex-shrink-0" />
                                <span>{tChat("completed")}</span>
                            </>
                        )}
                    </div>
                )}

                {/* Computer Stream Viewer */}
                {activeProgress?.browserStream && (
                    <ComputerViewer
                        stream={activeProgress.browserStream}
                        onClose={() => setBrowserStream(null)}
                        defaultExpanded={showBrowserStream}
                        collapsible={true}
                    />
                )}

                {/* Stage list */}
                {isExpanded ? (
                    <ScrollArea className="flex-1">
                        <div className="p-2 space-y-0.5">
                            {stageGroups.length === 0 && isStreaming && (
                                <div className="flex items-center gap-2 py-4 px-2 text-sm text-muted-foreground">
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                    <span>{tChat("thinking")}</span>
                                </div>
                            )}

                            {stageGroups.map((group, index) => (
                                <StageGroupItem
                                    key={`stage-${index}`}
                                    group={group}
                                    defaultExpanded={index === stageGroups.length - 1 || group.stage.status === "running"}
                                    isStreaming={isStreaming}
                                    agentType={agentType}
                                />
                            ))}

                            {/* Sources Section */}
                            {sources.length > 0 && (
                                <SourcesSection sources={sources} isExpanded={!isStreaming} />
                            )}
                        </div>
                    </ScrollArea>
                ) : (
                    /* Collapsed view - minimal list */
                    <ScrollArea className="flex-1">
                        <div className="p-2 space-y-0.5">
                            {stageGroups.length === 0 && isStreaming && (
                                <div className="flex items-center gap-2 py-2 px-2 text-sm text-muted-foreground">
                                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                    <span>{tChat("thinking")}</span>
                                </div>
                            )}

                            {stageGroups.map((group, index) => {
                                const hasTools = group.tools.length > 0;
                                const allToolsCompleted = hasTools && group.tools.every(t => t.endTimestamp || t.status === "completed");
                                const isStagePending = group.stage.status === "pending";
                                const isStageFailed = group.stage.status === "failed";
                                const isStageRunning = isStreaming && !isStagePending && !isStageFailed &&
                                                      group.stage.status === "running" &&
                                                      (!hasTools || group.tools.some(t => !t.endTimestamp && t.status !== "completed"));
                                const isStageCompleted = !isStagePending && !isStageRunning && !isStageFailed &&
                                                        (group.stage.status === "completed" ||
                                                         group.stage.endTimestamp !== undefined ||
                                                         allToolsCompleted ||
                                                         !isStreaming);

                                const stageDescription = getTranslatedStageDescription(group.stage, tStages, agentType);

                                return (
                                    <div
                                        key={`stage-collapsed-${index}`}
                                        className={cn(
                                            "flex items-center gap-2 px-2 py-1 text-sm",
                                            isStagePending && "text-muted-foreground/50",
                                            isStageRunning && "text-foreground",
                                            isStageCompleted && "text-muted-foreground",
                                            isStageFailed && "text-destructive"
                                        )}
                                    >
                                        <div className="w-4 h-4 flex items-center justify-center flex-shrink-0">
                                            {isStagePending ? (
                                                <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground/20" />
                                            ) : isStageRunning ? (
                                                <div className="w-2 h-2 rounded-full bg-foreground animate-pulse" />
                                            ) : isStageCompleted ? (
                                                <Check className="w-3.5 h-3.5 text-muted-foreground" />
                                            ) : isStageFailed ? (
                                                <div className="w-1.5 h-1.5 rounded-full bg-destructive" />
                                            ) : null}
                                        </div>
                                        <span className="truncate flex-1">{stageDescription}</span>
                                    </div>
                                );
                            })}

                            {sources.length > 0 && (
                                <div className="flex items-center gap-2 px-2 py-1 text-sm text-muted-foreground/70">
                                    <Globe className="w-3 h-3 flex-shrink-0" />
                                    <span>{tProgress("sourcesCount", { count: sources.length })}</span>
                                </div>
                            )}
                        </div>
                    </ScrollArea>
                )}
            </div>
        </>
    );
}
