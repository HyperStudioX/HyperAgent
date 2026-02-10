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

function getTypeLabel(type: PlanItem["type"]): string {
    switch (type) {
        case "tool":
            return "Tool";
        case "skill":
            return "Skill";
        case "browser":
            return "Browser";
        default:
            return "Step";
    }
}

function formatDuration(startMs: number, endMs?: number): string {
    const elapsed = (endMs || Date.now()) - startMs;
    if (elapsed < 1000) return "<1s";
    if (elapsed < 60000) return `${Math.round(elapsed / 1000)}s`;
    const mins = Math.floor(elapsed / 60000);
    const secs = Math.round((elapsed % 60000) / 1000);
    return `${mins}m ${secs}s`;
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
    item,
    isLast,
    nextItemTimestamp,
}: {
    item: PlanItem;
    isLast: boolean;
    nextItemTimestamp?: number;
}) {
    const [expanded, setExpanded] = useState(false);
    const [, setTick] = useState(0);
    const TypeIcon = getTypeIcon(item.type);

    // Tick every second for running items to update duration
    useEffect(() => {
        if (item.status !== "running") return;
        const interval = setInterval(() => setTick((t) => t + 1), 1000);
        return () => clearInterval(interval);
    }, [item.status]);

    const endTime = item.status === "running" ? undefined : nextItemTimestamp || item.timestamp;

    return (
        <div className="relative flex gap-3 group">
            {/* Timeline line */}
            {!isLast && (
                <div
                    className={cn(
                        "absolute left-[9px] top-6 bottom-0 w-px",
                        item.status === "completed"
                            ? "bg-green-500/20 dark:bg-green-400/20"
                            : item.status === "failed"
                              ? "bg-destructive/20"
                              : "bg-border/50"
                    )}
                />
            )}

            {/* Status dot */}
            <div className="flex-shrink-0 pt-0.5 z-[1]">
                <StatusIndicator status={item.status} type={item.type} />
            </div>

            {/* Content */}
            <div
                className={cn(
                    "flex-1 min-w-0 pb-4",
                    item.description && "cursor-pointer"
                )}
                onClick={() => item.description && setExpanded(!expanded)}
            >
                {/* Header row */}
                <div className="flex items-center gap-2 min-h-[20px]">
                    <div className={cn(
                        "flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium leading-none",
                        getTypeBgColor(item.type),
                        getTypeColor(item.type)
                    )}>
                        <TypeIcon className="w-2.5 h-2.5" />
                        <span>{getTypeLabel(item.type)}</span>
                    </div>

                    <span className={cn(
                        "text-sm truncate",
                        item.status === "completed" && "text-foreground/80",
                        item.status === "failed" && "text-destructive",
                        item.status === "running" && "text-foreground font-medium"
                    )}>
                        {item.name}
                    </span>

                    {/* Duration */}
                    <div className="flex items-center gap-1 ml-auto flex-shrink-0">
                        <Clock className="w-3 h-3 text-muted-foreground/50" />
                        <span className={cn(
                            "text-[11px] tabular-nums text-muted-foreground/60",
                            item.status === "running" && "text-muted-foreground"
                        )}>
                            {formatDuration(item.timestamp, endTime)}
                        </span>
                    </div>

                    {item.description && (
                        <ChevronDown className={cn(
                            "w-3 h-3 text-muted-foreground/40 transition-transform flex-shrink-0",
                            expanded && "rotate-180"
                        )} />
                    )}
                </div>

                {/* Running pulse indicator */}
                {item.status === "running" && (
                    <div className="mt-1.5 flex items-center gap-1.5">
                        <span className="relative flex h-1.5 w-1.5">
                            <span className={cn(
                                "animate-ping absolute inline-flex h-full w-full rounded-full opacity-75",
                                item.type === "tool" ? "bg-blue-500" :
                                item.type === "skill" ? "bg-purple-500" :
                                "bg-orange-500"
                            )} />
                            <span className={cn(
                                "relative inline-flex rounded-full h-1.5 w-1.5",
                                item.type === "tool" ? "bg-blue-500" :
                                item.type === "skill" ? "bg-purple-500" :
                                "bg-orange-500"
                            )} />
                        </span>
                        <span className="text-xs text-muted-foreground/70">In progress...</span>
                    </div>
                )}

                {/* Expandable description */}
                {item.description && expanded && (
                    <div className="mt-2 text-xs text-muted-foreground/80 leading-relaxed bg-muted/30 rounded px-2.5 py-2 border border-border/30">
                        {item.description}
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
                <div className="sticky top-0 z-10 bg-muted/50 border-b border-border/50 backdrop-blur-sm px-4 py-2.5">
                    <div className="flex items-center justify-between mb-1.5">
                        <div className="flex items-center gap-2">
                            <ListChecks className="w-3.5 h-3.5 text-muted-foreground" />
                            <span className="text-xs font-medium text-foreground">
                                {t("plan")}
                            </span>
                        </div>
                        {totalCount > 0 && (
                            <span className="text-xs text-muted-foreground tabular-nums">
                                {completedCount} of {totalCount} completed
                                {failedCount > 0 && (
                                    <span className="text-destructive ml-1">
                                        ({failedCount} failed)
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
                                    "h-full rounded-full transition-all duration-500",
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
                    {items.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-full min-h-[200px] text-muted-foreground">
                            <ListChecks className="w-8 h-8 mb-3 opacity-30" />
                            <p className="text-sm">{t("noPlanItems")}</p>
                            <p className="text-xs mt-1 opacity-70">{t("planItemsWillAppear")}</p>
                        </div>
                    ) : (
                        items.map((item, index) => (
                            <TimelineItem
                                key={item.id}
                                item={item}
                                isLast={index === items.length - 1}
                                nextItemTimestamp={items[index + 1]?.timestamp}
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
