"use client";

import React, { useState, useEffect, useMemo } from "react";
import { useTranslations } from "next-intl";
import { Check, AlertCircle, ChevronRight, Globe, ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";
import type { TimestampedEvent } from "@/lib/stores/agent-progress-store";
import type { Source, AgentEvent } from "@/lib/types";

// Union type for events - can be either timestamped (live) or plain (historical)
type ProgressEvent = TimestampedEvent | AgentEvent;

// Stage group containing a stage and its child tools
interface StageGroup {
    stage: ProgressEvent;
    stageIndex: number;
    tools: ProgressEvent[];
    startTime?: number; // Optional for historical events
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
    "computer", "context", "processing",
    // App builder stages
    "scaffold", "server"
];

/**
 * Helper to get timestamp from event (works for both TimestampedEvent and AgentEvent)
 */
function getEventTimestamp(event: ProgressEvent): number | undefined {
    return (event as TimestampedEvent).timestamp ?? event.timestamp;
}

function getEventEndTimestamp(event: ProgressEvent): number | undefined {
    return (event as TimestampedEvent).endTimestamp;
}

function groupEventsByStage(
    events: ProgressEvent[],
    processingLabel: string,
    isHistorical: boolean = false
): StageGroup[] {
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
        const eventTimestamp = getEventTimestamp(event);
        const eventEndTimestamp = getEventEndTimestamp(event);

        if ((event as unknown as { type: string }).type === "browser_action") {
            const browserEvent = event as unknown as Record<string, unknown>;
            const action = browserEvent.action as string;
            const description = browserEvent.description as string;
            const target = browserEvent.target as string | undefined;
            const rawStatus = (browserEvent.status as string) || "running";
            const effectiveStatus: AgentEvent["status"] = rawStatus === "failed"
                ? "failed"
                : (isHistorical ? "completed" : (rawStatus as AgentEvent["status"]));

            const stageName = `browser_${action}`;
            const stageEvent: ProgressEvent = {
                type: "stage",
                name: stageName,
                description: target ? `${description}: ${target}` : description,
                status: effectiveStatus,
                timestamp: eventTimestamp,
            };

            if (stageEvent.name && HIDDEN_STAGES.has(stageEvent.name)) continue;

            const name = stageEvent.name;
            if (name && stageGroupsByName[name]) {
                // Update existing group
                stageGroupsByName[name].stage = {
                    ...stageGroupsByName[name].stage,
                    status: stageEvent.status,
                };
                if (eventEndTimestamp || eventTimestamp) {
                    stageGroupsByName[name].endTime = eventEndTimestamp || eventTimestamp;
                }
            } else {
                currentGroup = {
                    stage: stageEvent,
                    stageIndex: i,
                    tools: [],
                    startTime: eventTimestamp,
                    endTime: eventEndTimestamp,
                };
                groups.push(currentGroup);
                if (name) stageGroupsByName[name] = currentGroup;
            }
            continue;
        }

        if (event.type === "stage") {
            if (event.name && HIDDEN_STAGES.has(event.name)) continue;

            // For historical events, treat everything as completed
            const effectiveStatus = event.status === "failed"
                ? "failed"
                : (isHistorical ? "completed" : event.status);

            if (event.status === "running" && !isHistorical) {
                currentGroup = {
                    stage: { ...event, status: effectiveStatus },
                    stageIndex: i,
                    tools: [],
                    startTime: eventTimestamp,
                    endTime: eventEndTimestamp,
                };
                groups.push(currentGroup);
                if (event.name) stageGroupsByName[event.name] = currentGroup;
            } else if (event.status === "completed" || event.status === "failed" || isHistorical) {
                const stageName = event.name;
                if (stageName && stageGroupsByName[stageName]) {
                    if (eventEndTimestamp || eventTimestamp) {
                        stageGroupsByName[stageName].endTime = eventEndTimestamp || eventTimestamp;
                    }
                    stageGroupsByName[stageName].stage = {
                        ...stageGroupsByName[stageName].stage,
                        status: effectiveStatus,
                    };
                } else {
                    currentGroup = {
                        stage: { ...event, status: effectiveStatus },
                        stageIndex: i,
                        tools: [],
                        startTime: eventTimestamp,
                        endTime: eventEndTimestamp || eventTimestamp,
                    };
                    groups.push(currentGroup);
                    if (stageName) stageGroupsByName[stageName] = currentGroup;
                }
            }
        } else if (event.type === "tool_call") {
            const toolKey = event.id || `${event.tool || event.name}-${i}`;
            if (seenToolIds.has(toolKey)) continue;
            seenToolIds.add(toolKey);

            const toolEvent: ProgressEvent = {
                ...event,
                // For historical events, mark tools as completed
                status: isHistorical ? "completed" : (
                    event.id && completedToolIds.has(event.id) ? "completed" : event.status
                ),
            };

            if (currentGroup) {
                currentGroup.tools.push(toolEvent);
            } else {
                const implicitGroup: StageGroup = {
                    stage: {
                        type: "stage",
                        name: "processing",
                        description: processingLabel,
                        status: isHistorical ? "completed" : "running",
                        timestamp: eventTimestamp,
                    },
                    stageIndex: -1,
                    tools: [toolEvent],
                    startTime: eventTimestamp,
                };
                groups.push(implicitGroup);
                currentGroup = implicitGroup;
            }
        }
    }

    return groups;
}

function getStageDescription(
    stage: ProgressEvent,
    tStages: ReturnType<typeof useTranslations>,
    agentType?: string,
    t?: ReturnType<typeof useTranslations>,
    tTools?: ReturnType<typeof useTranslations>
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

    // Check if description matches "Executing {tool}" pattern and translate it
    if (stage.description) {
        const executingMatch = stage.description.match(/^Executing (.+)$/i);
        if (executingMatch && t && tTools) {
            const toolNameRaw = executingMatch[1];
            // Convert tool name to key format (e.g., "Image Generation" -> "image_generation")
            // Handle both regular tools and skill tools
            let toolKey = toolNameRaw.toLowerCase().replace(/\s+/g, "_");
            
            // Check if it's a skill (starts with skill_ prefix in translations)
            const skillKey = `skill_${toolKey}`;
            let translatedToolName = toolNameRaw; // Fallback to original
            
            // Try to translate as skill first
            try {
                const skillTranslated = tTools(skillKey as Parameters<typeof tTools>[0]);
                if (skillTranslated && !skillTranslated.includes("chat.agent.tools")) {
                    translatedToolName = skillTranslated;
                } else {
                    // Try as regular tool
                    const toolTranslated = getToolDisplayName(toolKey, tTools);
                    if (toolTranslated && toolTranslated !== toolKey) {
                        translatedToolName = toolTranslated;
                    }
                }
            } catch {
                // Fall through
            }
            
            // Use the translation system for "Executing {tool}"
            try {
                return t("executing", { tool: translatedToolName });
            } catch {
                // Fall through to return original description
            }
        }
        return stage.description;
    }
    return stageName.charAt(0).toUpperCase() + stageName.slice(1).replace(/_/g, " ");
}

function getToolDisplayName(
    toolName: string,
    tTools?: ReturnType<typeof useTranslations>,
    skillId?: string
): string {
    // Special case: for invoke_skill, show the skill name instead
    if (toolName === "invoke_skill" && skillId) {
        // Try to get translation for the skill
        const skillToolKey = `skill_${skillId}`;
        if (tTools) {
            try {
                const translated = tTools(skillToolKey as Parameters<typeof tTools>[0]);
                if (translated && !translated.includes("chat.agent.tools")) {
                    return translated;
                }
            } catch {
                // Fall through
            }
        }
        // Fallback: format the skill_id nicely
        return skillId
            .replace(/_/g, " ")
            .replace(/([a-z])([A-Z])/g, "$1 $2")
            .toLowerCase()
            .replace(/^\w/, (c) => c.toUpperCase());
    }

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
        <span className="w-5 h-5 flex items-center justify-center">
            <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-40" />
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-primary" />
            </span>
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
    if (seconds < 60) return <span className="tabular-nums text-xs font-medium text-muted-foreground/70">{Math.floor(seconds)}s</span>;
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return <span className="tabular-nums text-xs font-medium text-muted-foreground/70">{minutes}:{secs.toString().padStart(2, '0')}</span>;
}

// Status indicator component
function StatusIndicator({ status }: { status: "pending" | "running" | "completed" | "failed" }) {
    if (status === "running") {
        return <PulsingDot />;
    }

    if (status === "completed") {
        return (
            <div className="w-5 h-5 rounded-full bg-emerald-500/20 flex items-center justify-center ring-1 ring-emerald-500/30">
                <Check className="w-3 h-3 text-emerald-600 dark:text-emerald-400" strokeWidth={2.5} />
            </div>
        );
    }

    if (status === "failed") {
        return (
            <div className="w-5 h-5 rounded-full bg-destructive/20 flex items-center justify-center ring-1 ring-destructive/30">
                <AlertCircle className="w-3 h-3 text-destructive" strokeWidth={2.5} />
            </div>
        );
    }

    return <div className="w-2.5 h-2.5 rounded-full bg-muted-foreground/25 ml-[5px]" />;
}

// Group tools by name and count them
interface GroupedTool {
    name: string;
    displayName: string;
    count: number;
    completedCount: number;
}

function groupTools(
    tools: ProgressEvent[],
    tTools?: ReturnType<typeof useTranslations>,
    isHistorical: boolean = false
): GroupedTool[] {
    const toolMap = new Map<string, GroupedTool>();

    for (const tool of tools) {
        const toolName = tool.tool || tool.name || "unknown";
        // For invoke_skill, extract the skill_id from args and use it as part of the key
        const skillId = toolName === "invoke_skill"
            ? (tool.args?.skill_id as string | undefined)
            : undefined;
        // Use skill_id in the key to group by specific skill
        const groupKey = skillId ? `invoke_skill:${skillId}` : toolName;

        const existing = toolMap.get(groupKey);
        const endTimestamp = getEventEndTimestamp(tool);
        const isCompleted = isHistorical || tool.status === "completed" || endTimestamp !== undefined;

        if (existing) {
            existing.count += 1;
            if (isCompleted) existing.completedCount += 1;
        } else {
            toolMap.set(groupKey, {
                name: groupKey,
                displayName: getToolDisplayName(toolName, tTools, skillId),
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
    isHistorical = false,
}: {
    label: string;
    status: "pending" | "running" | "completed" | "failed";
    duration?: { start?: number; end?: number };
    tools?: ProgressEvent[];
    tTools?: ReturnType<typeof useTranslations>;
    isLast: boolean;
    isHistorical?: boolean;
}) {
    const groupedTools = useMemo(() => {
        if (!tools || tools.length === 0) return [];
        return groupTools(tools, tTools, isHistorical);
    }, [tools, tTools, isHistorical]);

    const hasTools = groupedTools.length > 0;

    // Only show duration if we have valid timestamps and not in historical mode
    const showDuration = !isHistorical && duration?.start !== undefined;

    return (
        <div className="relative">
            {/* Vertical connector line - thicker, more visible */}
            {!isLast && (
                <div className="absolute left-[9px] top-7 bottom-0 w-[2px] bg-border/50" />
            )}

            <div className="flex items-start gap-4 py-2.5">
                {/* Status indicator */}
                <div className="flex-shrink-0 mt-0.5">
                    <StatusIndicator status={status} />
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                    <div className="flex items-baseline justify-between gap-3 mb-0.5">
                        <span className={cn(
                            "text-sm leading-snug font-medium tracking-tight",
                            status === "running" && "text-foreground",
                            status === "completed" && "text-muted-foreground/80",
                            status === "failed" && "text-destructive font-semibold",
                            status === "pending" && "text-muted-foreground/40"
                        )}>
                            {label}
                        </span>
                        {showDuration && duration?.start !== undefined && (
                            <div className="flex-shrink-0">
                                <LiveDuration startMs={duration.start} endMs={duration.end} />
                            </div>
                        )}
                    </div>

                    {/* Tools - vertical display, grouped by name */}
                    {hasTools && (
                        <div className="mt-2.5 space-y-1.5">
                            {groupedTools.map((groupedTool) => (
                                <div
                                    key={groupedTool.name}
                                    className="flex items-center gap-2.5 pl-0.5"
                                >
                                    <span className="w-1 h-1 rounded-full bg-muted-foreground/30 flex-shrink-0" />
                                    <span className="text-xs text-muted-foreground/70 leading-relaxed">
                                        {groupedTool.count > 1 ? (
                                            <>
                                                <span className="text-muted-foreground/50 tabular-nums font-medium">
                                                    {groupedTool.completedCount}/{groupedTool.count}
                                                </span>
                                                {" · "}{groupedTool.displayName}
                                            </>
                                        ) : (
                                            groupedTool.displayName
                                        )}
                                    </span>
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
        <div className="mt-4 pt-4 border-t border-border/50">
            <button
                className="flex items-center gap-2.5 w-full text-left group hover:opacity-80 transition-opacity"
                onClick={() => setIsExpanded(!isExpanded)}
            >
                <Globe className="w-4 h-4 text-muted-foreground/70" />
                <span className="flex-1 text-xs font-semibold text-muted-foreground/90 uppercase tracking-wider">
                    {tProgress("sourcesCount", { count: sources.length })}
                </span>
                <ChevronRight className={cn(
                    "w-4 h-4 text-muted-foreground/60 transition-transform duration-200",
                    isExpanded && "rotate-90"
                )} />
            </button>

            {isExpanded && (
                <div className="mt-3 space-y-0.5">
                    {sources.slice(0, 5).map((source) => (
                        <a
                            key={source.id}
                            href={source.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-2.5 py-2 px-2.5 -mx-2.5 rounded-md text-xs text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors group"
                        >
                            <ExternalLink className="w-3.5 h-3.5 flex-shrink-0 opacity-60 group-hover:opacity-100 transition-opacity" />
                            <span className="truncate leading-relaxed">{source.title}</span>
                        </a>
                    ))}
                    {sources.length > 5 && (
                        <div className="pt-2 pl-6">
                            <span className="text-[11px] text-muted-foreground/60 font-medium">
                                +{sources.length - 5} more sources
                            </span>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

interface TaskProgressPanelProps {
    events: ProgressEvent[];
    sources?: Source[];
    isStreaming?: boolean; // Optional - when false or undefined, treats as historical
    agentType?: string;
    className?: string;
}

/**
 * Task progress panel - displays inline within message bubbles
 * Handles both live streaming events and historical (saved) events
 * Clean, minimal design with clear visual hierarchy
 */
export function TaskProgressPanel({
    events,
    sources = [],
    isStreaming = false,
    agentType,
    className,
}: TaskProgressPanelProps) {
    // Historical mode: not streaming (completed or saved events)
    const isHistorical = !isStreaming;
    // Default to collapsed for historical events, expanded for live streaming
    const [isExpanded, setIsExpanded] = useState(!isHistorical);
    const tProgress = useTranslations("sidebar.progress");
    const t = useTranslations("chat.agent");
    const tStages = useTranslations("chat.agent.stages");
    const tTools = useTranslations("chat.agent.tools");

    const processingLabel = tProgress("processing");
    const stageGroups = useMemo(() => {
        return groupEventsByStage(events, processingLabel, isHistorical);
    }, [events, processingLabel, isHistorical]);

    const progressSummary = useMemo(() => {
        let completed = 0;
        let totalTools = 0;
        let hasError = false;

        for (const group of stageGroups) {
            if (group.stage.status === "failed") {
                hasError = true;
            }

            totalTools += group.tools.length;

            // In historical mode, everything is completed
            if (isHistorical) {
                if (group.stage.status !== "failed") {
                    completed++;
                }
                continue;
            }

            // Live mode: check actual completion status
            const hasTools = group.tools.length > 0;
            const allToolsCompleted = hasTools && group.tools.every(t => {
                const endTs = getEventEndTimestamp(t);
                return endTs !== undefined || t.status === "completed";
            });
            const stageEndTs = getEventEndTimestamp(group.stage);
            const isCompleted = !isStreaming ||
                group.stage.status === "completed" ||
                stageEndTs !== undefined ||
                allToolsCompleted;

            if (isCompleted && group.stage.status !== "failed") {
                completed++;
            }
        }

        return { completed, total: stageGroups.length, totalTools, hasError };
    }, [stageGroups, isStreaming, isHistorical]);

    // Build summary text for historical mode (like TaskProgressPanel did)
    // Must be before the early return to satisfy React hooks rules
    const summaryText = useMemo(() => {
        if (!isHistorical) return null;
        const parts: string[] = [];
        if (progressSummary.completed > 0) {
            parts.push(t("completedStages", { count: progressSummary.completed }));
        }
        if (progressSummary.totalTools > 0) {
            parts.push(t("toolsUsed", { count: progressSummary.totalTools }));
        }
        return parts.join(" · ") || t("completedStages", { count: 0 });
    }, [isHistorical, progressSummary, t]);

    if (stageGroups.length === 0) return null;

    return (
        <div className={cn(
            "rounded-lg border-2 border-border/60 bg-card overflow-hidden max-w-full",
            // Different margins for live vs historical
            isHistorical ? "mt-4" : "mt-4 mb-6",
            className
        )}>
            {/* Header */}
            <button
                className="flex items-center gap-3.5 !w-full px-5 py-3.5 text-left hover:bg-secondary/50 transition-colors"
                onClick={() => setIsExpanded(!isExpanded)}
            >
                {/* Status icon */}
                {isStreaming ? (
                    <PulsingDot />
                ) : progressSummary.hasError ? (
                    <div className="w-5 h-5 rounded-full bg-destructive/20 flex items-center justify-center ring-1 ring-destructive/30">
                        <AlertCircle className="w-3 h-3 text-destructive" strokeWidth={2.5} />
                    </div>
                ) : isHistorical ? (
                    // Muted icon for historical
                    <div className="w-5 h-5 rounded-full bg-muted flex items-center justify-center">
                        <Check className="w-3 h-3 text-muted-foreground" strokeWidth={2.5} />
                    </div>
                ) : (
                    <div className="w-5 h-5 rounded-full bg-emerald-500/20 flex items-center justify-center ring-1 ring-emerald-500/30">
                        <Check className="w-3 h-3 text-emerald-600 dark:text-emerald-400" strokeWidth={2.5} />
                    </div>
                )}

                {/* Title / Summary */}
                <span className={cn(
                    "flex-1 text-sm font-semibold tracking-tight",
                    isHistorical ? "text-muted-foreground/90" : "text-foreground"
                )}>
                    {isHistorical
                        ? summaryText
                        : (isStreaming ? tProgress("processing") : tProgress("completed"))
                    }
                </span>

                {/* Progress count - only show in live mode */}
                {!isHistorical && (
                    <div className="flex items-center gap-2">
                        <span className="text-xs tabular-nums font-semibold text-muted-foreground/80 px-2 py-1 rounded-md bg-muted/60">
                            {progressSummary.completed}/{progressSummary.total}
                        </span>
                    </div>
                )}

                {/* Expand chevron */}
                <ChevronRight className={cn(
                    "w-4 h-4 text-muted-foreground/60 transition-transform duration-200",
                    isExpanded && "rotate-90"
                )} />
            </button>

            {/* Content */}
            {isExpanded && (
                <div className="px-5 pb-5 pt-2 bg-background/30">
                    <div className="space-y-0">
                        {stageGroups.map((group, index) => {
                            const hasTools = group.tools.length > 0;
                            const allToolsCompleted = hasTools && group.tools.every(t => {
                                const endTs = getEventEndTimestamp(t);
                                return endTs !== undefined || t.status === "completed";
                            });

                            let status: "pending" | "running" | "completed" | "failed" = "pending";

                            if (group.stage.status === "failed") {
                                status = "failed";
                            } else if (isHistorical) {
                                // In historical mode, everything is completed
                                status = "completed";
                            } else {
                                const stageEndTs = getEventEndTimestamp(group.stage);
                                if (group.stage.status === "completed" ||
                                    stageEndTs !== undefined ||
                                    allToolsCompleted ||
                                    !isStreaming) {
                                    status = "completed";
                                } else if (group.stage.status === "running") {
                                    status = "running";
                                }
                            }

                            const label = getStageDescription(group.stage, tStages, agentType, t, tTools);

                            return (
                                <StageItem
                                    key={`stage-${index}`}
                                    label={label}
                                    status={status}
                                    duration={{ start: group.startTime, end: group.endTime }}
                                    tools={group.tools}
                                    tTools={tTools}
                                    isLast={index === stageGroups.length - 1}
                                    isHistorical={isHistorical}
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
