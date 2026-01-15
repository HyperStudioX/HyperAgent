"use client";

import React from "react";
import { Search, Brain, Sparkles, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface AgentProgressProps {
    status?: string | null;
    agentEvents?: any[];
    isStreaming?: boolean;
    className?: string;
}

export function AgentProgress({ status, agentEvents, isStreaming, className }: AgentProgressProps) {
    if (!isStreaming || (!status && (!agentEvents || agentEvents.length === 0))) {
        return null;
    }

    return (
        <div className={cn("flex flex-col gap-1.5 mb-4 w-full max-w-md", className)}>
            {agentEvents && agentEvents.map((event, i) => {
                const isLast = i === agentEvents.length - 1;
                return (
                    <div
                        key={i}
                        className={cn(
                            "flex items-center gap-2.5 px-3 py-1.5 rounded-lg border transition-colors duration-200 animate-slide-in-left",
                            isLast
                                ? "bg-secondary border-border shadow-sm"
                                : "bg-secondary/30 border-subtle opacity-70"
                        )}
                        style={{ animationDelay: `${i * 0.1}s`, animationFillMode: 'backwards' }}
                    >
                        <div className="flex-shrink-0">
                            {event.type === 'tool_call' ? (
                                <Search className={cn("w-3.5 h-3.5", isLast ? "text-foreground" : "text-muted-foreground")} />
                            ) : event.type === 'step' ? (
                                <Brain className={cn("w-3.5 h-3.5", isLast ? "text-foreground" : "text-muted-foreground")} />
                            ) : (
                                <Sparkles className={cn("w-3.5 h-3.5", isLast ? "text-foreground" : "text-muted-foreground")} />
                            )}
                        </div>
                        <span className={cn(
                            "text-xs font-medium truncate",
                            isLast ? "text-foreground" : "text-muted-foreground"
                        )}>
                            {event.type === 'tool_call'
                                ? `Searching: ${event.data?.args?.query || event.data?.tool || 'web'}...`
                                : event.data?.description || 'Processing...'}
                        </span>
                        {isLast && (
                            <div className="ml-auto pl-2">
                                <Loader2 className="w-3 h-3 animate-spin text-muted-foreground" />
                            </div>
                        )}
                    </div>
                );
            })}

            {!agentEvents && status && (
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-secondary border border-border w-fit animate-fade-in">
                    <Brain className="w-3.5 h-3.5 text-foreground animate-pulse" />
                    <span className="text-xs font-medium text-foreground">{status}</span>
                </div>
            )}
        </div>
    );
}
