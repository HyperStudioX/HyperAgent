"use client";

import React, { useState } from "react";
import { useTranslations } from "next-intl";
import {
    X,
    Check,
    Loader2,
    AlertCircle,
    ChevronDown,
    Globe,
    Link,
    Clock,
    Wrench,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { ResearchTask } from "@/lib/stores/task-store";
import type { Conversation, Source, ResearchStep, AgentEvent } from "@/lib/types";

interface TaskProgressModalProps {
    isOpen: boolean;
    onClose: () => void;
    item: { type: "task"; data: ResearchTask } | { type: "conversation"; data: Conversation };
}

// Format duration for display
function formatDuration(ms: number): string {
    const seconds = ms / 1000;
    if (seconds < 0.1) return "<0.1s";
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${minutes}m ${secs}s`;
}

// Step item component
function StepItem({
    label,
    status,
    duration,
}: {
    label: string;
    status: "pending" | "running" | "completed" | "failed";
    duration?: string;
}) {
    return (
        <div className="flex items-center gap-3 py-2.5">
            {/* Status icon */}
            <div className="w-5 h-5 flex items-center justify-center flex-shrink-0">
                {status === "pending" && (
                    <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground/30" />
                )}
                {status === "running" && (
                    <Loader2 className="w-4 h-4 text-muted-foreground animate-spin" />
                )}
                {status === "completed" && (
                    <Check className="w-4 h-4 text-green-600 dark:text-green-500" strokeWidth={2} />
                )}
                {status === "failed" && (
                    <AlertCircle className="w-4 h-4 text-destructive" />
                )}
            </div>

            {/* Label */}
            <span className={cn(
                "flex-1 text-sm",
                status === "pending" && "text-muted-foreground/50",
                status === "running" && "text-foreground",
                status === "completed" && "text-foreground",
                status === "failed" && "text-destructive"
            )}>
                {label}
            </span>

            {/* Duration */}
            {duration && (
                <span className="text-xs tabular-nums text-muted-foreground/50">
                    {duration}
                </span>
            )}
        </div>
    );
}

// Sources section
function SourcesSection({ sources }: { sources: Source[] }) {
    const [isExpanded, setIsExpanded] = useState(false);
    const tProgress = useTranslations("sidebar.progress");

    if (sources.length === 0) return null;

    return (
        <div className="mt-3 pt-3 border-t border-border/30">
            <button
                className="flex items-center gap-3 py-2 w-full text-left"
                onClick={() => setIsExpanded(!isExpanded)}
            >
                <Globe className="w-4 h-4 text-muted-foreground/60 flex-shrink-0" />
                <span className="flex-1 text-sm text-muted-foreground">
                    {tProgress("sourcesCount", { count: sources.length })}
                </span>
                <ChevronDown className={cn(
                    "w-4 h-4 text-muted-foreground/50 transition-transform",
                    isExpanded && "rotate-180"
                )} />
            </button>

            {isExpanded && (
                <div className="ml-8 space-y-1.5 pb-2">
                    {sources.map((source) => (
                        <a
                            key={source.id}
                            href={source.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-2 py-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
                        >
                            <Link className="w-3 h-3 flex-shrink-0" />
                            <span className="truncate">{source.title || source.url}</span>
                        </a>
                    ))}
                </div>
            )}
        </div>
    );
}

// Research task progress view
function ResearchTaskProgress({ task }: { task: ResearchTask }) {
    const tSteps = useTranslations("task.steps");
    const tProgress = useTranslations("sidebar.progress");

    // Calculate total duration
    const totalDuration = task.updatedAt && task.createdAt
        ? new Date(task.updatedAt).getTime() - new Date(task.createdAt).getTime()
        : 0;

    // Map steps to display format
    const displaySteps = task.steps.map((step: ResearchStep) => ({
        label: tSteps(`${step.type}.${step.status}`) || step.description,
        status: step.status,
    }));

    // Progress summary
    const hasErrors = task.steps.some((s: ResearchStep) => s.status === "failed");

    return (
        <div className="space-y-1">
            {/* Steps list */}
            {displaySteps.map((step, index) => (
                <StepItem
                    key={index}
                    label={step.label}
                    status={step.status}
                />
            ))}

            {/* Show placeholder if no steps */}
            {displaySteps.length === 0 && (
                <div className="py-6 text-center text-sm text-muted-foreground">
                    {tProgress("processing")}
                </div>
            )}

            {/* Sources */}
            <SourcesSection sources={task.sources || []} />

            {/* Footer with summary */}
            {task.status === "completed" || task.status === "failed" ? (
                <div className={cn(
                    "mt-4 pt-3 border-t border-border/30 flex items-center gap-2",
                    hasErrors ? "text-destructive" : "text-muted-foreground"
                )}>
                    {hasErrors ? (
                        <AlertCircle className="w-4 h-4" />
                    ) : (
                        <Check className="w-4 h-4 text-green-600 dark:text-green-500" />
                    )}
                    <span className="text-sm flex-1">
                        {hasErrors
                            ? tProgress("completedWithErrors")
                            : tProgress("completed")}
                    </span>
                    {totalDuration > 0 && (
                        <span className="flex items-center gap-1.5 text-xs text-muted-foreground/50">
                            <Clock className="w-3 h-3" />
                            {formatDuration(totalDuration)}
                        </span>
                    )}
                </div>
            ) : null}
        </div>
    );
}

// Tool item component
function ToolItem({ name }: { name: string }) {
    // Format tool name for display
    const displayName = name
        .replace(/_/g, " ")
        .replace(/([a-z])([A-Z])/g, "$1 $2")
        .toLowerCase()
        .replace(/^\w/, (c) => c.toUpperCase());

    return (
        <div className="flex items-center gap-2 py-1.5 ml-1">
            <Wrench className="w-3.5 h-3.5 text-muted-foreground/60 flex-shrink-0" />
            <span className="text-sm text-foreground/70">{displayName}</span>
        </div>
    );
}

// Tools section
function ToolsSection({ tools }: { tools: AgentEvent[] }) {
    const [isExpanded, setIsExpanded] = useState(false);
    const tProgress = useTranslations("sidebar.progress");

    if (tools.length === 0) return null;

    return (
        <div className="mt-3 pt-3 border-t border-border/30">
            <button
                className="flex items-center gap-3 py-2 w-full text-left"
                onClick={() => setIsExpanded(!isExpanded)}
            >
                <Wrench className="w-4 h-4 text-muted-foreground/60 flex-shrink-0" />
                <span className="flex-1 text-sm text-muted-foreground">
                    {tProgress("toolCount", { count: tools.length })}
                </span>
                <ChevronDown className={cn(
                    "w-4 h-4 text-muted-foreground/50 transition-transform",
                    isExpanded && "rotate-180"
                )} />
            </button>

            {isExpanded && (
                <div className="ml-6 space-y-0.5 pb-2">
                    {tools.map((tool, index) => (
                        <ToolItem
                            key={`tool-${index}`}
                            name={tool.tool || tool.name || "unknown"}
                        />
                    ))}
                </div>
            )}
        </div>
    );
}

// Chat conversation progress view - shows message events if available
function ConversationProgress({ conversation }: { conversation: Conversation }) {
    const tProgress = useTranslations("sidebar.progress");
    const tStages = useTranslations("chat.agent.stages");

    // Find messages with saved agent events
    const messagesWithEvents = conversation.messages.filter(
        (msg) => msg.metadata?.agentEvents && msg.metadata.agentEvents.length > 0
    );

    if (messagesWithEvents.length === 0) {
        return (
            <div className="py-8 text-center">
                <p className="text-sm text-muted-foreground">
                    {tProgress("noProgressAvailable") || "Detailed progress not available for this conversation."}
                </p>
                <p className="text-xs text-muted-foreground/60 mt-2">
                    {tProgress("progressNotSaved") || "Agent events are only saved during streaming."}
                </p>
            </div>
        );
    }

    // Display saved events from the most recent message with events
    const latestWithEvents = messagesWithEvents[messagesWithEvents.length - 1];
    const events = latestWithEvents.metadata?.agentEvents || [];

    // Group events by type
    const stageEvents = events.filter((e: AgentEvent) => e.type === "stage");
    const toolEvents = events.filter((e: AgentEvent) => e.type === "tool_call");

    return (
        <div className="space-y-1">
            {stageEvents.map((event: AgentEvent, index: number) => {
                const stageName = event.name || "default";
                const status = event.status || "completed";

                // Try to get translated label
                let label = event.description || stageName;
                try {
                    const key = `${stageName}.${status}` as Parameters<typeof tStages>[0];
                    const translatedLabel = tStages(key);
                    // Check if translation exists (next-intl returns the key path if translation is missing)
                    if (translatedLabel && !translatedLabel.includes("chat.agent.stages")) {
                        label = translatedLabel;
                    }
                } catch {
                    // Use default label if translation fails
                }

                return (
                    <StepItem
                        key={`${stageName}-${index}`}
                        label={label}
                        status={status}
                    />
                );
            })}

            {/* Tools section */}
            <ToolsSection tools={toolEvents} />

            {/* Sources from message metadata */}
            {latestWithEvents.metadata?.sources && (
                <SourcesSection sources={latestWithEvents.metadata.sources} />
            )}
        </div>
    );
}

export function TaskProgressModal({ isOpen, onClose, item }: TaskProgressModalProps) {
    const tProgress = useTranslations("sidebar.progress");

    if (!isOpen) return null;

    const title = item.type === "task" ? item.data.query : item.data.title;

    return (
        <>
            {/* Backdrop */}
            <div
                className="fixed inset-0 bg-black/40 z-50 animate-in fade-in duration-200"
                onClick={onClose}
            />

            {/* Modal */}
            <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
                <div
                    className={cn(
                        "bg-background border border-border rounded-xl shadow-lg",
                        "w-full max-w-md max-h-[80vh] overflow-hidden",
                        "animate-in zoom-in-95 fade-in duration-200"
                    )}
                    onClick={(e) => e.stopPropagation()}
                >
                    {/* Header */}
                    <div className="flex items-center justify-between px-4 py-3 border-b border-border">
                        <div className="flex-1 min-w-0 pr-4">
                            <h2 className="text-sm font-medium text-foreground truncate">
                                {tProgress("taskProgress")}
                            </h2>
                            <p className="text-xs text-muted-foreground truncate mt-0.5">
                                {title.slice(0, 60) + (title.length > 60 ? "..." : "")}
                            </p>
                        </div>
                        <button
                            onClick={onClose}
                            className="p-1.5 -m-1.5 rounded-md hover:bg-secondary transition-colors"
                        >
                            <X className="w-4 h-4 text-muted-foreground" />
                        </button>
                    </div>

                    {/* Content */}
                    <div className="p-4 overflow-y-auto max-h-[calc(80vh-60px)]">
                        {item.type === "task" ? (
                            <ResearchTaskProgress task={item.data} />
                        ) : (
                            <ConversationProgress conversation={item.data} />
                        )}
                    </div>
                </div>
            </div>
        </>
    );
}
