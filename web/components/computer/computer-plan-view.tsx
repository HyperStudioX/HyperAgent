"use client";

import React, { useRef, useEffect } from "react";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import { FileText } from "lucide-react";
import { useTranslations } from "next-intl";
import type { PlanItem } from "@/lib/stores/computer-store";

interface ComputerPlanViewProps {
    items: PlanItem[];
    className?: string;
}

function getStatusMarker(status: PlanItem["status"]): string {
    switch (status) {
        case "running":
            return "[ ]";
        case "completed":
            return "[x]";
        case "failed":
            return "[!]";
        default:
            return "[ ]";
    }
}

function getTypePrefix(type: PlanItem["type"]): string {
    switch (type) {
        case "tool":
            return "tool:";
        case "skill":
            return "skill:";
        case "browser":
            return "browser:";
        default:
            return "";
    }
}

function PlanLine({
    item,
    lineNumber,
    isLast
}: {
    item: PlanItem;
    lineNumber: number;
    isLast: boolean;
}) {
    const marker = getStatusMarker(item.status);
    const prefix = getTypePrefix(item.type);

    return (
        <div className={cn(
            "flex font-mono text-sm leading-6 group",
            item.status === "running" && "bg-muted/30"
        )}>
            {/* Line number */}
            <span className="w-10 flex-shrink-0 text-right pr-3 text-muted-foreground/50 select-none">
                {lineNumber}
            </span>

            {/* Content */}
            <div className="flex-1 min-w-0">
                <span className={cn(
                    item.status === "completed" && "text-green-600 dark:text-green-500",
                    item.status === "failed" && "text-destructive",
                    item.status === "running" && "text-foreground"
                )}>
                    {marker}
                </span>
                <span className="text-muted-foreground ml-1">{prefix}</span>
                <span className={cn(
                    "ml-1",
                    item.status === "completed" && "text-muted-foreground",
                    item.status === "failed" && "text-destructive",
                    item.status === "running" && "text-foreground font-medium"
                )}>
                    {item.name}
                </span>
                {/* Typing cursor for running items */}
                {item.status === "running" && isLast && (
                    <span className="inline-block w-2 h-4 bg-foreground/70 ml-0.5 animate-pulse" />
                )}
            </div>
        </div>
    );
}

function DescriptionLine({
    description,
    lineNumber,
    status,
}: {
    description: string;
    lineNumber: number;
    status: PlanItem["status"];
}) {
    return (
        <div className={cn(
            "flex font-mono text-sm leading-6",
            status === "running" && "bg-muted/30"
        )}>
            {/* Line number */}
            <span className="w-10 flex-shrink-0 text-right pr-3 text-muted-foreground/50 select-none">
                {lineNumber}
            </span>

            {/* Content - indented description */}
            <div className="flex-1 min-w-0 pl-6">
                <span className="text-muted-foreground/70 italic">
                    # {description}
                </span>
            </div>
        </div>
    );
}

export function ComputerPlanView({
    items,
    className,
}: ComputerPlanViewProps) {
    const t = useTranslations("computer");
    const scrollRef = useRef<HTMLDivElement>(null);
    const bottomRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom when new items are added
    useEffect(() => {
        if (bottomRef.current) {
            bottomRef.current.scrollIntoView({ behavior: "smooth" });
        }
    }, [items.length]);

    // Calculate line numbers with descriptions
    let lineNumber = 0;
    const lines: React.ReactNode[] = [];

    items.forEach((item, index) => {
        lineNumber++;
        lines.push(
            <PlanLine
                key={`${item.id}-main`}
                item={item}
                lineNumber={lineNumber}
                isLast={index === items.length - 1}
            />
        );

        if (item.description) {
            lineNumber++;
            lines.push(
                <DescriptionLine
                    key={`${item.id}-desc`}
                    description={item.description}
                    lineNumber={lineNumber}
                    status={item.status}
                />
            );
        }
    });

    return (
        <ScrollArea className={cn("flex-1 bg-background", className)}>
            <div ref={scrollRef} className="min-h-full">
                {/* File header */}
                <div className="sticky top-0 z-10 flex items-center gap-2 px-3 py-2 bg-muted/50 border-b border-border/50 backdrop-blur-sm">
                    <FileText className="w-3.5 h-3.5 text-muted-foreground" />
                    <span className="text-xs font-mono text-muted-foreground">PLAN.md</span>
                    {items.length > 0 && (
                        <span className="text-xs text-muted-foreground/50 ml-auto">
                            {items.filter(i => i.status === "completed").length}/{items.length}
                        </span>
                    )}
                </div>

                {/* File content */}
                <div className="py-2">
                    {items.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-full min-h-[200px] text-muted-foreground">
                            <FileText className="w-8 h-8 mb-3 opacity-30" />
                            <p className="text-sm font-mono">{t("noPlanItems")}</p>
                            <p className="text-xs mt-1 opacity-70">{t("planItemsWillAppear")}</p>
                        </div>
                    ) : (
                        <>
                            {/* Header comment */}
                            <div className="flex font-mono text-sm leading-6 text-muted-foreground/50">
                                <span className="w-10 flex-shrink-0 text-right pr-3 select-none">1</span>
                                <span># Agent Execution Plan</span>
                            </div>
                            <div className="flex font-mono text-sm leading-6 text-muted-foreground/30">
                                <span className="w-10 flex-shrink-0 text-right pr-3 select-none">2</span>
                                <span></span>
                            </div>

                            {/* Re-render lines with adjusted line numbers */}
                            {items.map((item, index) => {
                                const baseLineNum = 3 + index * (item.description ? 2 : 1);
                                const prevDescCount = items.slice(0, index).filter(i => i.description).length;
                                const actualLineNum = 3 + index + prevDescCount;

                                return (
                                    <React.Fragment key={item.id}>
                                        <PlanLine
                                            item={item}
                                            lineNumber={actualLineNum}
                                            isLast={index === items.length - 1}
                                        />
                                        {item.description && (
                                            <DescriptionLine
                                                description={item.description}
                                                lineNumber={actualLineNum + 1}
                                                status={item.status}
                                            />
                                        )}
                                    </React.Fragment>
                                );
                            })}
                        </>
                    )}
                </div>

                {/* Scroll anchor */}
                <div ref={bottomRef} />
            </div>
        </ScrollArea>
    );
}
