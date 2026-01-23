"use client";

import React, { useState, useMemo } from "react";
import { useTranslations } from "next-intl";
import { Check, ChevronRight, AlertCircle, Zap } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AgentEvent } from "@/lib/types";

// Group tools by name and count them
interface GroupedTool {
    name: string;
    displayName: string;
    count: number;
}

interface AgentProgressPanelProps {
    events: AgentEvent[];
    className?: string;
}

// Stage group containing a stage and its child tools
interface StageGroup {
    stage: AgentEvent;
    tools: AgentEvent[];
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

/**
 * Group events by stage - tools are nested under their parent stage
 * For saved events (message bubble), all items should show as completed
 */
function groupEventsByStage(events: AgentEvent[]): StageGroup[] {
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

        if (event.type === "browser_action") {
            const action = event.action || "unknown";
            const description = event.description || "";
            const target = event.target;
            const status = event.status || "completed";

            const stageName = `browser_${action}`;
            const stageEvent: AgentEvent = {
                type: "stage",
                name: stageName,
                description: target ? `${description}: ${target}` : description,
                status: status === "failed" ? "failed" : "completed",
            };

            if (stageEvent.name && HIDDEN_STAGES.has(stageEvent.name)) continue;

            const name = stageEvent.name;
            if (name && stageGroupsByName[name]) {
                stageGroupsByName[name].stage = {
                    ...stageGroupsByName[name].stage,
                    status: stageEvent.status,
                };
            } else {
                currentGroup = {
                    stage: stageEvent,
                    tools: [],
                };
                groups.push(currentGroup);
                if (name) stageGroupsByName[name] = currentGroup;
            }
            continue;
        }

        if (event.type === "stage") {
            if (event.name && HIDDEN_STAGES.has(event.name)) continue;

            const stageName = event.name;
            const effectiveStatus = event.status === "failed" ? "failed" : "completed";

            if (stageName && stageGroupsByName[stageName]) {
                stageGroupsByName[stageName].stage = {
                    ...stageGroupsByName[stageName].stage,
                    status: effectiveStatus,
                };
            } else {
                currentGroup = {
                    stage: { ...event, status: effectiveStatus },
                    tools: [],
                };
                groups.push(currentGroup);
                if (stageName) stageGroupsByName[stageName] = currentGroup;
            }
        } else if (event.type === "tool_call") {
            const toolKey = event.id || `${event.tool || event.name}-${i}`;
            if (seenToolIds.has(toolKey)) continue;
            seenToolIds.add(toolKey);

            const toolEvent: AgentEvent = {
                ...event,
                status: "completed",
            };

            if (currentGroup) {
                currentGroup.tools.push(toolEvent);
            } else {
                const implicitGroup: StageGroup = {
                    stage: {
                        type: "stage",
                        name: "processing",
                        status: "completed",
                    },
                    tools: [toolEvent],
                };
                groups.push(implicitGroup);
                currentGroup = implicitGroup;
            }
        }
    }

    return groups;
}

function getStageDescription(
    stage: AgentEvent,
    tStages: ReturnType<typeof useTranslations>,
    agentType?: string
): string {
    const stageName = stage.name || "processing";
    const status = stage.status || "completed";

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
    tTools: ReturnType<typeof useTranslations>
): string {
    try {
        const translated = tTools(toolName as Parameters<typeof tTools>[0]);
        if (translated && !translated.includes("chat.agent.tools")) {
            return translated;
        }
    } catch {
        // Fall through
    }

    return toolName
        .replace(/_/g, " ")
        .replace(/([a-z])([A-Z])/g, "$1 $2")
        .toLowerCase()
        .replace(/^\w/, (c) => c.toUpperCase());
}

function groupTools(tools: AgentEvent[], tTools: ReturnType<typeof useTranslations>): GroupedTool[] {
    const toolMap = new Map<string, GroupedTool>();

    for (const tool of tools) {
        const toolName = tool.tool || tool.name || "unknown";
        const existing = toolMap.get(toolName);

        if (existing) {
            existing.count += 1;
        } else {
            toolMap.set(toolName, {
                name: toolName,
                displayName: getToolDisplayName(toolName, tTools),
                count: 1,
            });
        }
    }

    return Array.from(toolMap.values());
}

// Status indicator for completed states
function StatusIndicator({ status }: { status: string }) {
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

/**
 * Agent progress panel - shows expandable progress steps and tools
 * Used in message bubbles to display saved agent events
 * Clean, minimal design matching the live panel
 */
export function AgentProgressPanel({ events, className }: AgentProgressPanelProps) {
    const [isExpanded, setIsExpanded] = useState(false);
    const t = useTranslations("chat.agent");
    const tStages = useTranslations("chat.agent.stages");
    const tTools = useTranslations("chat.agent.tools");

    const stageGroups = useMemo(() => groupEventsByStage(events), [events]);

    const summary = useMemo(() => {
        let completedStages = 0;
        let totalTools = 0;
        let hasError = false;

        for (const group of stageGroups) {
            if (group.stage.status === "completed") completedStages++;
            if (group.stage.status === "failed") hasError = true;
            totalTools += group.tools.length;
        }

        return { completedStages, totalTools, hasError, totalStages: stageGroups.length };
    }, [stageGroups]);

    if (stageGroups.length === 0) return null;

    // Build summary text
    const summaryParts: string[] = [];
    if (summary.completedStages > 0) {
        summaryParts.push(t("completedStages", { count: summary.completedStages }));
    }
    if (summary.totalTools > 0) {
        summaryParts.push(t("toolsUsed", { count: summary.totalTools }));
    }
    const summaryText = summaryParts.join(" · ") || t("completedStages", { count: 0 });

    return (
        <div className={cn("mt-4 rounded-xl border border-border/60 bg-card/50 overflow-hidden max-w-md", className)}>
            {/* Header button */}
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="flex items-center gap-3 w-full px-4 py-3 text-left hover:bg-muted/30 transition-colors"
            >
                {/* Icon */}
                <div className="w-4 h-4 rounded-full bg-muted/80 flex items-center justify-center">
                    <Zap className="w-2.5 h-2.5 text-muted-foreground" />
                </div>

                {/* Summary text */}
                <span className="flex-1 text-[13px] font-medium text-muted-foreground">
                    {summaryText}
                </span>

                {/* Expand chevron */}
                <ChevronRight
                    className={cn(
                        "w-4 h-4 text-muted-foreground/50 transition-transform duration-200",
                        isExpanded && "rotate-90"
                    )}
                />
            </button>

            {/* Expanded content */}
            {isExpanded && (
                <div className="px-4 pb-4 pt-1">
                    <div className="space-y-0">
                        {stageGroups.map((group, groupIndex) => {
                            const status = group.stage.status || "completed";
                            const stageLabel = getStageDescription(group.stage, tStages);
                            const groupedTools = groupTools(group.tools, tTools);
                            const hasTools = groupedTools.length > 0;
                            const isLast = groupIndex === stageGroups.length - 1;

                            return (
                                <div key={`group-${groupIndex}`} className="relative">
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
                                            <span className={cn(
                                                "text-[13px] leading-relaxed",
                                                status === "completed" && "text-muted-foreground",
                                                status === "failed" && "text-red-600 dark:text-red-400"
                                            )}>
                                                {stageLabel}
                                            </span>

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
                                                                        ({groupedTool.count})
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
                        })}
                    </div>
                </div>
            )}
        </div>
    );
}
