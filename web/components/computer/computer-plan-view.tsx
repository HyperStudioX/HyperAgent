"use client";

import React, { useRef, useEffect, useState, useMemo } from "react";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
    ListChecks,
    Wrench,
    Sparkles,
    Globe,
    Check,
    AlertCircle,
    Loader2,
    ChevronDown,
    Clock,
} from "lucide-react";
import { useTranslations } from "next-intl";
import type { PlanItem } from "@/lib/stores/computer-store";

/**
 * A grouped plan item that collapses consecutive items with the same name+type.
 */
interface GroupedPlanItem {
    /** Use the first item's id as group key */
    id: string;
    type: PlanItem["type"];
    name: string;
    /** Number of items collapsed into this group */
    count: number;
    /** Aggregated status: running if any is running, failed if any failed, else completed */
    status: PlanItem["status"];
    /** Earliest timestamp in the group */
    startTimestamp: number;
    /** Latest timestamp in the group (used for duration calculation) */
    lastTimestamp: number;
    /** Description from the first item */
    description?: string;
    /** All individual items in this group (for potential expansion) */
    items: PlanItem[];
}

/**
 * Group consecutive plan items that share the same name and type.
 * Non-consecutive duplicates are NOT merged — only adjacent runs are collapsed.
 */
function groupConsecutivePlanItems(items: PlanItem[]): GroupedPlanItem[] {
    if (items.length === 0) return [];

    const groups: GroupedPlanItem[] = [];
    let current: GroupedPlanItem | null = null;

    for (const item of items) {
        if (current && current.name === item.name && current.type === item.type) {
            // Extend the current group
            current.count += 1;
            current.items.push(item);
            current.lastTimestamp = item.timestamp;
            // Aggregate status: running wins over completed, failed wins over all
            if (item.status === "failed") {
                current.status = "failed";
            } else if (item.status === "running" && current.status !== "failed") {
                current.status = "running";
            }
        } else {
            // Start a new group
            current = {
                id: item.id,
                type: item.type,
                name: item.name,
                count: 1,
                status: item.status,
                startTimestamp: item.timestamp,
                lastTimestamp: item.timestamp,
                description: item.description,
                items: [item],
            };
            groups.push(current);
        }
    }

    return groups;
}

interface ComputerPlanViewProps {
    items: PlanItem[];
    className?: string;
}

function getTypeIcon(type: PlanItem["type"]) {
    switch (type) {
        case "tool":
            return Wrench;
        case "skill":
            return Sparkles;
        case "browser":
            return Globe;
        default:
            return Wrench;
    }
}

function renderTypeIcon(type: PlanItem["type"], className: string) {
    const Icon = getTypeIcon(type);
    return <Icon className={className} />;
}

/* Semantic plan-type colors - intentionally using distinct colors per type for visual differentiation */
function getTypeColor(type: PlanItem["type"]): string {
    switch (type) {
        case "tool":
            return "text-blue-600 dark:text-blue-400";
        case "skill":
            return "text-purple-600 dark:text-purple-400";
        case "browser":
            return "text-orange-600 dark:text-orange-400";
        default:
            return "text-muted-foreground";
    }
}

/* Semantic plan-type background colors - intentionally using distinct colors per type */
function getTypeBgColor(type: PlanItem["type"]): string {
    switch (type) {
        case "tool":
            return "bg-blue-500/10 dark:bg-blue-400/10";
        case "skill":
            return "bg-purple-500/10 dark:bg-purple-400/10";
        case "browser":
            return "bg-orange-500/10 dark:bg-orange-400/10";
        default:
            return "bg-muted";
    }
}

function getTypeLabelKey(type: PlanItem["type"]): string {
    switch (type) {
        case "tool":
            return "planType.tool";
        case "skill":
            return "planType.skill";
        case "browser":
            return "planType.browser";
        default:
            return "planType.step";
    }
}

function safeTranslateTool(
    tTools: ReturnType<typeof useTranslations>,
    toolKey: string
): string | null {
    if (!toolKey) return null;
    try {
        const translated = tTools(toolKey as never);
        if (!translated || translated === toolKey) return null;
        return translated;
    } catch {
        return null;
    }
}

function getDisplayName(
    group: GroupedPlanItem,
    t: ReturnType<typeof useTranslations>,
    tTools: ReturnType<typeof useTranslations>
): string {
    const rawName = group.name || "";

    if (group.type === "tool") {
        return (
            safeTranslateTool(tTools, rawName) ||
            safeTranslateTool(tTools, "default") ||
            rawName
        );
    }

    if (group.type === "skill") {
        return (
            safeTranslateTool(tTools, `skill_${rawName}`) ||
            safeTranslateTool(tTools, rawName) ||
            t("planName.skillInvocation")
        );
    }

    if (group.type === "browser") {
        return (
            safeTranslateTool(tTools, `browser_${rawName}`) ||
            t("planName.browserAction")
        );
    }

    return rawName || t("planType.step");
}

function getDisplayDescription(
    group: GroupedPlanItem,
    t: ReturnType<typeof useTranslations>,
    tTools: ReturnType<typeof useTranslations>
): string | undefined {
    const rawName = group.name || "";
    const translatedName = getDisplayName(group, t, tTools);
    const rawDescription = group.description?.trim();

    // Backward compatibility for older persisted English descriptions
    if (rawDescription) {
        const invokeMatch = rawDescription.match(/^Invoking skill:\s*(.+)$/i);
        if (invokeMatch) {
            return t("planAction.invokingSkill", { skill: invokeMatch[1] });
        }
        const callToolMatch = rawDescription.match(/^Calling tool:\s*(.+)$/i);
        if (callToolMatch) {
            const translatedTool =
                safeTranslateTool(tTools, callToolMatch[1]) || callToolMatch[1];
            return t("planAction.callingTool", { tool: translatedTool });
        }
        const navigateMatch = rawDescription.match(/^Navigating to:\s*(.+)$/i);
        if (navigateMatch) {
            return t("planAction.navigatingTo", { target: navigateMatch[1] });
        }
        const clickMatch = rawDescription.match(/^Clicking:\s*(.+)$/i);
        if (clickMatch) {
            return t("planAction.clicking", { target: clickMatch[1] });
        }
        const typeMatch = rawDescription.match(/^Typing:\s*\"(.+)\"$/i);
        if (typeMatch) {
            return t("planAction.typing", { text: typeMatch[1] });
        }
        return rawDescription;
    }

    if (group.type === "skill") {
        return t("planAction.invokingSkill", { skill: translatedName });
    }
    if (group.type === "tool") {
        return t("planAction.callingTool", { tool: translatedName });
    }
    if (group.type === "browser") {
        return t("planAction.browserAction");
    }
    if (rawName) {
        return translatedName;
    }
    return undefined;
}

function formatDuration(startMs: number, endMs: number | undefined, t: (key: string, params?: Record<string, string | number | Date>) => string): string {
    const elapsed = (endMs || Date.now()) - startMs;
    if (elapsed < 1000) return t("duration.lessThanSecond");
    if (elapsed < 60000) return t("duration.seconds", { count: Math.round(elapsed / 1000) });
    const mins = Math.floor(elapsed / 60000);
    const secs = Math.round((elapsed % 60000) / 1000);
    return t("duration.minutesSeconds", { min: mins, sec: secs });
}

function StatusIndicator({ status, type }: { status: PlanItem["status"]; type: PlanItem["type"] }) {
    switch (status) {
        case "completed":
            return (
                <div className="w-5 h-5 rounded-full bg-green-500/15 dark:bg-green-400/15 flex items-center justify-center">
                    <Check className="w-3 h-3 text-green-600 dark:text-green-500" />
                </div>
            );
        case "failed":
            return (
                <div className="w-5 h-5 rounded-full bg-destructive/15 flex items-center justify-center">
                    <AlertCircle className="w-3 h-3 text-destructive" />
                </div>
            );
        case "running":
            return (
                <div className={cn("w-5 h-5 rounded-full flex items-center justify-center", getTypeBgColor(type))}>
                    <Loader2 className={cn("w-3 h-3 animate-spin", getTypeColor(type))} />
                </div>
            );
        default:
            return (
                <div className="w-5 h-5 rounded-full bg-muted flex items-center justify-center">
                    <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground/40" />
                </div>
            );
    }
}

function TimelineItem({
    group,
    isLast,
    nextGroupTimestamp,
}: {
    group: GroupedPlanItem;
    isLast: boolean;
    nextGroupTimestamp?: number;
}) {
    const t = useTranslations("computer");
    const tTools = useTranslations("chat.agent.tools");
    const [expanded, setExpanded] = useState(false);
    const [, setTick] = useState(0);
    const displayName = useMemo(() => getDisplayName(group, t, tTools), [group, t, tTools]);
    const displayDescription = useMemo(
        () => getDisplayDescription(group, t, tTools),
        [group, t, tTools]
    );

    // Tick every second for running items to update duration
    useEffect(() => {
        if (group.status !== "running") return;
        const interval = setInterval(() => setTick((t) => t + 1), 1000);
        return () => clearInterval(interval);
    }, [group.status]);

    const endTime = group.status === "running" ? undefined : nextGroupTimestamp || group.lastTimestamp;

    return (
        <div className="relative flex gap-3 group/timeline">
            {/* Timeline line */}
            {!isLast && (
                <div
                    className={cn(
                        "absolute left-[9px] top-6 bottom-0 w-px",
                        group.status === "completed"
                            ? "bg-green-500/20 dark:bg-green-400/20"
                            : group.status === "failed"
                              ? "bg-destructive/20"
                              : "bg-border/50"
                    )}
                />
            )}

            {/* Status dot */}
            <div className="flex-shrink-0 pt-0.5 z-[1]">
                <StatusIndicator status={group.status} type={group.type} />
            </div>

            {/* Content */}
            <div
                className={cn(
                    "flex-1 min-w-0 pb-4",
                    displayDescription && "cursor-pointer"
                )}
                onClick={() => displayDescription && setExpanded(!expanded)}
            >
                {/* Header row */}
                <div className="flex items-center gap-2 min-h-[20px]">
                    <div className={cn(
                        "flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium leading-none",
                        getTypeBgColor(group.type),
                        getTypeColor(group.type)
                    )}>
                        {renderTypeIcon(group.type, "w-2.5 h-2.5")}
                        <span>{t(getTypeLabelKey(group.type))}</span>
                    </div>

                    <span className={cn(
                        "text-sm truncate",
                        group.status === "completed" && "text-foreground/80",
                        group.status === "failed" && "text-destructive",
                        group.status === "running" && "text-foreground font-medium"
                    )}>
                        {displayName}
                    </span>

                    {/* Count badge for grouped items */}
                    {group.count > 1 && (
                        <span className="text-[10px] tabular-nums font-medium text-muted-foreground/60 bg-muted/60 px-1.5 py-0.5 rounded-full leading-none flex-shrink-0">
                            ×{group.count}
                        </span>
                    )}

                    {/* Duration */}
                    <div className="flex items-center gap-1 ml-auto flex-shrink-0">
                        <Clock className="w-3 h-3 text-muted-foreground/50" />
                        <span className={cn(
                            "text-[11px] tabular-nums text-muted-foreground/60",
                            group.status === "running" && "text-muted-foreground"
                        )}>
                            {formatDuration(group.startTimestamp, endTime, t)}
                        </span>
                    </div>

                    {displayDescription && (
                        <ChevronDown className={cn(
                            "w-3 h-3 text-muted-foreground/40 transition-transform flex-shrink-0",
                            expanded && "rotate-180"
                        )} />
                    )}
                </div>

                {/* Running pulse indicator */}
                {group.status === "running" && (
                    <div className="mt-1.5 flex items-center gap-1.5">
                        <span className="relative flex h-1.5 w-1.5">
                            <span className={cn(
                                "animate-ping absolute inline-flex h-full w-full rounded-full opacity-75",
                                group.type === "tool" ? "bg-blue-500" :
                                group.type === "skill" ? "bg-purple-500" :
                                "bg-orange-500"
                            )} />
                            <span className={cn(
                                "relative inline-flex rounded-full h-1.5 w-1.5",
                                group.type === "tool" ? "bg-blue-500" :
                                group.type === "skill" ? "bg-purple-500" :
                                "bg-orange-500"
                            )} />
                        </span>
                        <span className="text-xs text-muted-foreground/70">{t("planInProgress")}</span>
                    </div>
                )}

                {/* Expandable description */}
                {displayDescription && expanded && (
                    <div className="mt-2 text-xs text-muted-foreground/80 leading-relaxed bg-muted/30 rounded px-2.5 py-2 border border-border/30">
                        {displayDescription}
                    </div>
                )}
            </div>
        </div>
    );
}

export function ComputerPlanView({
    items,
    className,
}: ComputerPlanViewProps) {
    const t = useTranslations("computer");
    const bottomRef = useRef<HTMLDivElement>(null);

    // Group consecutive items with the same name+type to reduce visual clutter
    const groupedItems = useMemo(() => groupConsecutivePlanItems(items), [items]);

    const completedCount = useMemo(() => items.filter((i) => i.status === "completed").length, [items]);
    const failedCount = useMemo(() => items.filter((i) => i.status === "failed").length, [items]);
    const totalCount = items.length;
    const progressPercent = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

    // Auto-scroll to bottom when new items are added
    useEffect(() => {
        if (bottomRef.current) {
            bottomRef.current.scrollIntoView({ behavior: "smooth" });
        }
    }, [items.length]);

    return (
        <ScrollArea className={cn("flex-1 bg-background", className)}>
            <div className="min-h-full">
                {/* Progress summary header */}
                <div className="sticky top-0 z-10 bg-background/95 border-b border-border/50 px-4 py-2.5">
                    <div className="flex items-center justify-between mb-1.5">
                        <div className="flex items-center gap-2">
                            <ListChecks className="w-3.5 h-3.5 text-muted-foreground" />
                            <span className="text-xs font-medium text-foreground">
                                {t("plan")}
                            </span>
                        </div>
                        {totalCount > 0 && (
                            <span className="text-xs text-muted-foreground tabular-nums">
                                {t("planProgress", { completed: completedCount, total: totalCount })}
                                {failedCount > 0 && (
                                    <span className="text-destructive ml-1">
                                        ({t("planFailed", { count: failedCount })})
                                    </span>
                                )}
                            </span>
                        )}
                    </div>

                    {/* Progress bar */}
                    {totalCount > 0 && (
                        <div className="h-1 bg-border/30 rounded-full overflow-hidden">
                            <div
                                className={cn(
                                    "h-full rounded-full transition-colors duration-500",
                                    failedCount > 0
                                        ? "bg-destructive/70"
                                        : completedCount === totalCount
                                          ? "bg-green-500 dark:bg-green-400"
                                          : "bg-foreground/30"
                                )}
                                style={{ width: `${progressPercent}%` }}
                            />
                        </div>
                    )}
                </div>

                {/* Timeline content */}
                <div className="px-4 pt-3 pb-2">
                    {groupedItems.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-full min-h-[200px] text-muted-foreground">
                            <ListChecks className="w-8 h-8 mb-3 opacity-30" />
                            <p className="text-sm">{t("noPlanItems")}</p>
                            <p className="text-xs mt-1 opacity-70">{t("planItemsWillAppear")}</p>
                        </div>
                    ) : (
                        groupedItems.map((group, index) => (
                            <TimelineItem
                                key={group.id}
                                group={group}
                                isLast={index === groupedItems.length - 1}
                                nextGroupTimestamp={groupedItems[index + 1]?.startTimestamp}
                            />
                        ))
                    )}
                </div>

                {/* Scroll anchor */}
                <div ref={bottomRef} />
            </div>
        </ScrollArea>
    );
}
