"use client";

import React, { useState, useEffect, useMemo } from "react";
import { useTranslations } from "next-intl";
import { Check, AlertCircle, ChevronRight, Globe, ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";
import type { TimestampedEvent } from "@/lib/stores/agent-progress-store";
import type { Source } from "@/lib/types";

// Stage group containing a stage and its child tools
interface StageGroup {
    stage: TimestampedEvent;
    stageIndex: number;
    tools: TimestampedEvent[];
    startTime: number;
    endTime?: number;
}

// Internal stages to hide from the UI
const HIDDEN_STAGES = new Set(["thinking", "routing"]);

// Known stage names for translation
const KNOWN_STAGES = [
    "handoff", "chat", "analyze", "search", "tool", "write", "synthesize",
    "research", "plan", "generate", "execute", "summarize", "finalize",
    "outline", "data", "source", "code_result", "config", "search_tools",
    "collect", "report", "thinking", "routing", "refine", "present",
    "analyze_image", "generate_image",
    "browser_launch", "browser_navigate", "browser_click", "browser_type",
    "browser_screenshot", "browser_scroll", "browser_key", "browser_computer",
    "computer", "context", "processing"
];

function groupEventsByStage(events: TimestampedEvent[], processingLabel: string): StageGroup[] {
    const groups: StageGroup[] = [];
    let currentGroup: StageGroup | null = null;
    const stageGroupsByName: Record<string, StageGroup> = {};
    const seenToolIds = new Set<string>();
    const completedToolIds = new Set<string>();

    for (const event of events) {
        if (event.type === "tool_result" && event.id) {
            completedToolIds.add(event.id);
        }
    }

    for (let i = 0; i < events.length; i++) {
        const event = events[i];

        if ((event as unknown as { type: string }).type === "browser_action") {
            const browserEvent = event as unknown as Record<string, unknown>;
            const action = browserEvent.action as string;
            const description = browserEvent.description as string;
            const target = browserEvent.target as string | undefined;
            const status = (browserEvent.status as string) || "running";

            const stageName = `browser_${action}`;
            const stageEvent: TimestampedEvent = {
                type: "stage",
                name: stageName,
                description: target ? `${description}: ${target}` : description,
                status: status === "completed" ? "completed" : "running",
                timestamp: event.timestamp,
                endTimestamp: event.endTimestamp,
            };

            if (stageEvent.name && HIDDEN_STAGES.has(stageEvent.name)) continue;

            if (stageEvent.status === "running") {
                currentGroup = {
                    stage: stageEvent,
                    stageIndex: i,
                    tools: [],
                    startTime: stageEvent.timestamp,
                    endTime: stageEvent.endTimestamp,
                };
                groups.push(currentGroup);
                if (stageEvent.name) stageGroupsByName[stageEvent.name] = currentGroup;
            } else if (stageEvent.status === "completed" || stageEvent.status === "failed") {
                const name = stageEvent.name;
                if (name && stageGroupsByName[name]) {
                    stageGroupsByName[name].endTime = stageEvent.endTimestamp || stageEvent.timestamp;
                    stageGroupsByName[name].stage = {
                        ...stageGroupsByName[name].stage,
                        status: stageEvent.status,
                        endTimestamp: stageEvent.endTimestamp || stageEvent.timestamp,
                    };
                }
            }
            continue;
        }

        if (event.type === "stage") {
            if (event.name && HIDDEN_STAGES.has(event.name)) continue;

            if (event.status === "running") {
                currentGroup = {
                    stage: event,
                    stageIndex: i,
                    tools: [],
                    startTime: event.timestamp,
                    endTime: event.endTimestamp,
                };
                groups.push(currentGroup);
                if (event.name) stageGroupsByName[event.name] = currentGroup;
            } else if (event.status === "completed" || event.status === "failed") {
                const stageName = event.name;
                if (stageName && stageGroupsByName[stageName]) {
                    stageGroupsByName[stageName].endTime = event.endTimestamp || event.timestamp;
                    stageGroupsByName[stageName].stage = {
                        ...stageGroupsByName[stageName].stage,
                        status: event.status,
                        endTimestamp: event.endTimestamp || event.timestamp,
                    };
                } else {
                    currentGroup = {
                        stage: event,
                        stageIndex: i,
                        tools: [],
                        startTime: event.timestamp,
                        endTime: event.endTimestamp || event.timestamp,
                    };
                    groups.push(currentGroup);
                    if (stageName) stageGroupsByName[stageName] = currentGroup;
                }
            }
        } else if (event.type === "tool_call") {
            const toolKey = event.id || `${event.tool || event.name}-${event.timestamp}`;
            if (seenToolIds.has(toolKey)) continue;
            seenToolIds.add(toolKey);

            const toolEvent = { ...event };
            if (event.id && completedToolIds.has(event.id)) {
                toolEvent.status = "completed";
            }

            if (currentGroup) {
                currentGroup.tools.push(toolEvent);
            } else {
                const implicitGroup: StageGroup = {
                    stage: {
                        type: "stage",
                        name: "processing",
                        description: processingLabel,
                        status: "running",
                        timestamp: event.timestamp,
                    },
                    stageIndex: -1,
                    tools: [toolEvent],
                    startTime: event.timestamp,
                };
                groups.push(implicitGroup);
                currentGroup = implicitGroup;
            }
        }
    }

    return groups;
}

function getStageDescription(
    stage: TimestampedEvent,
    tStages: ReturnType<typeof useTranslations>,
    agentType?: string
): string {
    const stageName = stage.name || "processing";
    const status = stage.status || "running";

    if (agentType === "image") {
        if (stageName === "analyze" || stageName === "generate") {
            try {
                const key = `${stageName}_image.${status}` as Parameters<typeof tStages>[0];
                const translated = tStages(key);
                if (translated && translated !== key && !translated.includes(`${stageName}_image`)) {
                    return translated;
                }
            } catch {
                // Fall through
            }
        }
    }

    if (KNOWN_STAGES.includes(stageName)) {
        try {
            const key = `${stageName}.${status}` as Parameters<typeof tStages>[0];
            const translated = tStages(key);
            if (translated && translated.trim() && translated !== key && !translated.startsWith("chat.agent.stages")) {
                return translated;
            }
        } catch {
            // Fall through
        }
    }

    if (stage.description) return stage.description;
    return stageName.charAt(0).toUpperCase() + stageName.slice(1).replace(/_/g, " ");
}

function getToolDisplayName(
    toolName: string,
    tTools?: ReturnType<typeof useTranslations>
): string {
    if (tTools) {
        try {
            const translated = tTools(toolName as Parameters<typeof tTools>[0]);
            if (translated && !translated.includes("chat.agent.tools")) {
                return translated;
            }
        } catch {
            // Fall through
        }
    }

    return toolName
        .replace(/_/g, " ")
        .replace(/([a-z])([A-Z])/g, "$1 $2")
        .toLowerCase()
        .replace(/^\w/, (c) => c.toUpperCase());
}

// Animated pulsing dot for running state
function PulsingDot() {
    return (
        <span className="w-4 h-4 flex items-center justify-center">
            <span className="w-2 h-2 rounded-full bg-primary/80 animate-pulse" />
        </span>
    );
}

// Live duration with clean formatting
function LiveDuration({ startMs, endMs }: { startMs: number; endMs?: number }) {
    const [now, setNow] = useState(() => Date.now());

    useEffect(() => {
        if (endMs) return;
        const interval = setInterval(() => setNow(Date.now()), 1000);
        return () => clearInterval(interval);
    }, [endMs]);

    const duration = endMs ? endMs - startMs : now - startMs;
    const seconds = duration / 1000;

    if (seconds < 1) return null;
    if (seconds < 60) return <span className="tabular-nums text-[11px] text-muted-foreground/60">{Math.floor(seconds)}s</span>;
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return <span className="tabular-nums text-[11px] text-muted-foreground/60">{minutes}:{secs.toString().padStart(2, '0')}</span>;
}

// Status indicator component
function StatusIndicator({ status }: { status: "pending" | "running" | "completed" | "failed" }) {
    if (status === "running") {
        return <PulsingDot />;
    }

    if (status === "completed") {
        return (
            <div className="w-4 h-4 rounded-full bg-emerald-500/15 flex items-center justify-center">
                <Check className="w-2.5 h-2.5 text-emerald-600 dark:text-emerald-400" strokeWidth={3} />
            </div>
        );
    }

    if (status === "failed") {
        return (
            <div className="w-4 h-4 rounded-full bg-red-500/15 flex items-center justify-center">
                <AlertCircle className="w-2.5 h-2.5 text-red-600 dark:text-red-400" strokeWidth={2.5} />
            </div>
        );
    }

    return <div className="w-2 h-2 rounded-full bg-muted-foreground/20" />;
}

// Group tools by name and count them
interface GroupedTool {
    name: string;
    displayName: string;
    count: number;
    completedCount: number;
}

function groupTools(tools: TimestampedEvent[], tTools?: ReturnType<typeof useTranslations>): GroupedTool[] {
    const toolMap = new Map<string, GroupedTool>();

    for (const tool of tools) {
        const toolName = tool.tool || tool.name || "unknown";
        const existing = toolMap.get(toolName);
        const isCompleted = tool.status === "completed" || tool.endTimestamp !== undefined;

        if (existing) {
            existing.count += 1;
            if (isCompleted) existing.completedCount += 1;
        } else {
            toolMap.set(toolName, {
                name: toolName,
                displayName: getToolDisplayName(toolName, tTools),
                count: 1,
                completedCount: isCompleted ? 1 : 0,
            });
        }
    }

    return Array.from(toolMap.values());
}

// Stage item with tools
function StageItem({
    label,
    status,
    duration,
    tools,
    tTools,
    isLast,
}: {
    label: string;
    status: "pending" | "running" | "completed" | "failed";
    duration?: { start: number; end?: number };
    tools?: TimestampedEvent[];
    tTools?: ReturnType<typeof useTranslations>;
    isLast: boolean;
}) {
    const groupedTools = useMemo(() => {
        if (!tools || tools.length === 0) return [];
        return groupTools(tools, tTools);
    }, [tools, tTools]);

    const hasTools = groupedTools.length > 0;

    return (
        <div className="relative">
            {/* Vertical connector line */}
            {!isLast && (
                <div className="absolute left-[7px] top-6 bottom-0 w-px bg-border/40" />
            )}

            <div className="flex items-start gap-3 py-2">
                {/* Status indicator */}
                <div className="flex-shrink-0 mt-[3px]">
                    <StatusIndicator status={status} />
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2.5">
                        <span className={cn(
                            "text-[13px] leading-relaxed",
                            status === "running" && "text-foreground font-medium",
                            status === "completed" && "text-muted-foreground",
                            status === "failed" && "text-red-600 dark:text-red-400",
                            status === "pending" && "text-muted-foreground/50"
                        )}>
                            {label}
                        </span>
                        {duration && (
                            <LiveDuration startMs={duration.start} endMs={duration.end} />
                        )}
                    </div>

                    {/* Tools - vertical display, grouped by name */}
                    {hasTools && (
                        <div className="mt-2 ml-0.5 space-y-1.5 border-l border-border/30 pl-3">
                            {groupedTools.map((groupedTool) => (
                                <div
                                    key={groupedTool.name}
                                    className="flex items-center gap-2 text-[11px] leading-relaxed text-muted-foreground/60"
                                >
                                    <span className="w-1 h-1 rounded-full bg-muted-foreground/25 flex-shrink-0" />
                                    {groupedTool.count > 1 ? (
                                        <span>
                                            <span className="text-muted-foreground/40 tabular-nums">
                                                ({groupedTool.completedCount}/{groupedTool.count})
                                            </span>
                                            {" "}{groupedTool.displayName}
                                        </span>
                                    ) : (
                                        <span>{groupedTool.displayName}</span>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

// Sources section
function SourcesSection({ sources }: { sources: Source[] }) {
    const [isExpanded, setIsExpanded] = useState(false);
    const tProgress = useTranslations("sidebar.progress");

    if (sources.length === 0) return null;

    return (
        <div className="mt-3 pt-3 border-t border-border/40">
            <button
                className="flex items-center gap-2 w-full text-left group"
                onClick={() => setIsExpanded(!isExpanded)}
            >
                <Globe className="w-3.5 h-3.5 text-muted-foreground/60" />
                <span className="flex-1 text-[12px] font-medium text-muted-foreground">
                    {tProgress("sourcesCount", { count: sources.length })}
                </span>
                <ChevronRight className={cn(
                    "w-3.5 h-3.5 text-muted-foreground/50 transition-transform duration-200",
                    isExpanded && "rotate-90"
                )} />
            </button>

            {isExpanded && (
                <div className="mt-2 space-y-1">
                    {sources.slice(0, 5).map((source) => (
                        <a
                            key={source.id}
                            href={source.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-2 py-1 px-2 -mx-2 rounded text-[11px] text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors group"
                        >
                            <ExternalLink className="w-3 h-3 flex-shrink-0 opacity-50 group-hover:opacity-100" />
                            <span className="truncate">{source.title}</span>
                        </a>
                    ))}
                    {sources.length > 5 && (
                        <span className="block text-[10px] text-muted-foreground/50 pl-5">
                            +{sources.length - 5} more
                        </span>
                    )}
                </div>
            )}
        </div>
    );
}

interface LiveAgentProgressPanelProps {
    events: TimestampedEvent[];
    sources?: Source[];
    isStreaming: boolean;
    agentType?: string;
    className?: string;
}

/**
 * Live agent progress panel - displays inline within the streaming message bubble
 * Clean, minimal design with clear visual hierarchy
 */
export function LiveAgentProgressPanel({
    events,
    sources = [],
    isStreaming,
    agentType,
    className,
}: LiveAgentProgressPanelProps) {
    const [isExpanded, setIsExpanded] = useState(true);
    const tProgress = useTranslations("sidebar.progress");
    const tStages = useTranslations("chat.agent.stages");
    const tTools = useTranslations("chat.agent.tools");

    const processingLabel = tProgress("processing");
    const stageGroups = useMemo(() => {
        return groupEventsByStage(events, processingLabel);
    }, [events, processingLabel]);

    const progressSummary = useMemo(() => {
        let completed = 0;
        let hasError = false;

        for (const group of stageGroups) {
            if (group.stage.status === "failed") {
                hasError = true;
            }

            const hasTools = group.tools.length > 0;
            const allToolsCompleted = hasTools && group.tools.every(t => t.endTimestamp || t.status === "completed");
            const isCompleted = !isStreaming ||
                group.stage.status === "completed" ||
                group.stage.endTimestamp !== undefined ||
                allToolsCompleted;

            if (isCompleted && group.stage.status !== "failed") {
                completed++;
            }
        }

        return { completed, total: stageGroups.length, hasError };
    }, [stageGroups, isStreaming]);

    if (stageGroups.length === 0) return null;

    return (
        <div className={cn(
            "mb-4 rounded-xl border-2 border-border/80 bg-card/50 overflow-hidden max-w-md",
            className
        )}>
            {/* Header */}
            <button
                className="flex items-center gap-3 w-full px-4 py-3 text-left hover:bg-muted/30 transition-colors"
                onClick={() => setIsExpanded(!isExpanded)}
            >
                {/* Status icon */}
                {isStreaming ? (
                    <PulsingDot />
                ) : progressSummary.hasError ? (
                    <div className="w-4 h-4 rounded-full bg-red-500/15 flex items-center justify-center">
                        <AlertCircle className="w-2.5 h-2.5 text-red-600 dark:text-red-400" />
                    </div>
                ) : (
                    <div className="w-4 h-4 rounded-full bg-emerald-500/15 flex items-center justify-center">
                        <Check className="w-2.5 h-2.5 text-emerald-600 dark:text-emerald-400" strokeWidth={3} />
                    </div>
                )}

                {/* Title */}
                <span className="flex-1 text-[13px] font-medium text-foreground">
                    {isStreaming ? tProgress("processing") : tProgress("completed")}
                </span>

                {/* Progress count */}
                <span className="text-[12px] tabular-nums text-muted-foreground">
                    {progressSummary.completed}/{progressSummary.total}
                </span>

                {/* Expand chevron */}
                <ChevronRight className={cn(
                    "w-4 h-4 text-muted-foreground/50 transition-transform duration-200",
                    isExpanded && "rotate-90"
                )} />
            </button>

            {/* Content */}
            {isExpanded && (
                <div className="px-4 pb-4 pt-1">
                    <div className="space-y-0">
                        {stageGroups.map((group, index) => {
                            const hasTools = group.tools.length > 0;
                            const allToolsCompleted = hasTools &&
                                group.tools.every(t => t.endTimestamp || t.status === "completed");

                            let status: "pending" | "running" | "completed" | "failed" = "pending";

                            if (group.stage.status === "failed") {
                                status = "failed";
                            } else if (group.stage.status === "completed" ||
                                       group.stage.endTimestamp !== undefined ||
                                       allToolsCompleted ||
                                       !isStreaming) {
                                status = "completed";
                            } else if (group.stage.status === "running") {
                                status = "running";
                            }

                            const label = getStageDescription(group.stage, tStages, agentType);

                            return (
                                <StageItem
                                    key={`stage-${index}`}
                                    label={label}
                                    status={status}
                                    duration={{ start: group.startTime, end: group.endTime }}
                                    tools={group.tools}
                                    tTools={tTools}
                                    isLast={index === stageGroups.length - 1}
                                />
                            );
                        })}
                    </div>

                    <SourcesSection sources={sources} />
                </div>
            )}
        </div>
    );
}
