"use client";

import React, { useRef, useEffect } from "react";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { TerminalLine } from "@/lib/stores/computer-store";

interface ComputerTerminalViewProps {
    lines: TerminalLine[];
    currentStep?: number;
    isLive?: boolean;
    className?: string;
}

function TerminalLineContent({ line }: { line: TerminalLine }) {
    switch (line.type) {
        case "prompt":
            return (
                <div className="flex items-start gap-0">
                    <span className="text-terminal-prompt font-semibold">
                        ubuntu@sandbox
                    </span>
                    <span className="text-terminal-fg">:</span>
                    <span className="text-blue-400">{line.cwd || "~"}</span>
                    <span className="text-terminal-fg">$ </span>
                </div>
            );

        case "command":
            return (
                <div className="flex items-start">
                    <span className="text-terminal-prompt font-semibold">
                        ubuntu@sandbox
                    </span>
                    <span className="text-terminal-fg">:</span>
                    <span className="text-blue-400">{line.cwd || "~"}</span>
                    <span className="text-terminal-fg">$ </span>
                    <span className="text-terminal-command">{line.content}</span>
                </div>
            );

        case "output":
            return (
                <div className="text-terminal-output whitespace-pre-wrap break-all">
                    {line.content}
                </div>
            );

        case "error":
            return (
                <div className="text-terminal-error whitespace-pre-wrap break-all">
                    {line.content}
                </div>
            );

        default:
            return (
                <div className="text-terminal-fg whitespace-pre-wrap break-all">
                    {line.content}
                </div>
            );
    }
}

export function ComputerTerminalView({
    lines,
    currentStep,
    isLive = true,
    className,
}: ComputerTerminalViewProps) {
    const scrollRef = useRef<HTMLDivElement>(null);
    const bottomRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom when new lines are added (only when live)
    useEffect(() => {
        if (isLive && bottomRef.current) {
            bottomRef.current.scrollIntoView({ behavior: "smooth" });
        }
    }, [lines.length, isLive]);

    // Filter lines based on current step for playback
    const visibleLines = currentStep !== undefined && !isLive
        ? lines.slice(0, currentStep)
        : lines;

    return (
        <ScrollArea className={cn("flex-1 bg-terminal-bg", className)}>
            <div
                ref={scrollRef}
                className="p-3 font-mono text-sm leading-relaxed min-h-full"
            >
                {visibleLines.length === 0 ? (
                    <div className="text-terminal-output/50 italic">
                        No terminal output yet...
                    </div>
                ) : (
                    visibleLines.map((line) => (
                        <div
                            key={line.id}
                            className="py-0.5 hover:bg-white/5 transition-colors rounded px-1 -mx-1"
                        >
                            <TerminalLineContent line={line} />
                        </div>
                    ))
                )}

                {/* Current prompt when live and idle */}
                {isLive && visibleLines.length > 0 && (
                    <div className="py-0.5 px-1 -mx-1 flex items-center">
                        <span className="text-terminal-prompt font-semibold">
                            ubuntu@sandbox
                        </span>
                        <span className="text-terminal-fg">:</span>
                        <span className="text-blue-400">~</span>
                        <span className="text-terminal-fg">$ </span>
                        <span className="w-2 h-4 bg-terminal-fg/70 animate-pulse ml-0.5" />
                    </div>
                )}

                {/* Scroll anchor */}
                <div ref={bottomRef} />
            </div>
        </ScrollArea>
    );
}
