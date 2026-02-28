"use client";

import React, { useRef, useEffect, useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";
import {
    Copy,
    Check,
    Trash2,
    WrapText,
    Loader2,
    TerminalSquare,
} from "lucide-react";
import { useTranslations } from "next-intl";
import type { TerminalLine } from "@/lib/stores/computer-store";

interface ComputerTerminalViewProps {
    lines: TerminalLine[];
    isLive?: boolean;
    currentCommand?: string | null;
    currentCwd?: string;
    onClear?: () => void;
    onSendCommand?: (command: string) => void;
    className?: string;
}

function CopyButton({ text }: { text: string }) {
    const [copied, setCopied] = useState(false);
    const t = useTranslations("computer");

    const handleCopy = useCallback(
        async (e: React.MouseEvent) => {
            e.stopPropagation();
            try {
                await navigator.clipboard.writeText(text);
                setCopied(true);
                setTimeout(() => setCopied(false), 1500);
            } catch {
                // Clipboard API may not be available
            }
        },
        [text]
    );

    return (
        <TooltipProvider delayDuration={300}>
            <Tooltip>
                <TooltipTrigger asChild>
                    <button
                        onClick={handleCopy}
                        className={cn(
                            "p-1 rounded transition-colors",
                            "opacity-0 group-hover:opacity-100",
                            "text-terminal-output/50 hover:text-terminal-fg",
                            "hover:bg-accent"
                        )}
                        aria-label={t("copyCommand")}
                    >
                        {copied ? (
                            <Check className="w-3.5 h-3.5 text-terminal-prompt" />
                        ) : (
                            <Copy className="w-3.5 h-3.5" />
                        )}
                    </button>
                </TooltipTrigger>
                <TooltipContent side="top">
                    {copied ? t("copied") : t("copyCommand")}
                </TooltipContent>
            </Tooltip>
        </TooltipProvider>
    );
}

function TerminalPrompt({ cwd }: { cwd?: string }) {
    return (
        <>
            <span className="text-terminal-prompt font-semibold">
                ubuntu@sandbox
            </span>
            <span className="text-terminal-fg">:</span>
            <span className="text-terminal-command">{cwd || "~"}</span>
            <span className="text-terminal-fg">$ </span>
        </>
    );
}

function TerminalLineContent({
    line,
    wordWrap,
}: {
    line: TerminalLine;
    wordWrap: boolean;
}) {
    const wrapClass = wordWrap
        ? "whitespace-pre-wrap break-all"
        : "whitespace-pre overflow-x-auto";

    switch (line.type) {
        case "prompt":
            return (
                <div className="flex items-start gap-0">
                    <TerminalPrompt cwd={line.cwd} />
                </div>
            );

        case "command":
            return (
                <div className="group flex items-start justify-between gap-2">
                    <div className="flex items-start min-w-0">
                        <TerminalPrompt cwd={line.cwd} />
                        <span
                            className={cn("text-terminal-command", wrapClass)}
                        >
                            {line.content}
                        </span>
                    </div>
                    <CopyButton text={line.content} />
                </div>
            );

        case "output":
            return (
                <div className={cn("text-terminal-output", wrapClass)}>
                    {line.content}
                </div>
            );

        case "error":
            return (
                <div className={cn("text-terminal-error", wrapClass)}>
                    {line.content}
                </div>
            );

        default:
            return (
                <div className={cn("text-terminal-fg", wrapClass)}>
                    {line.content}
                </div>
            );
    }
}

export function ComputerTerminalView({
    lines,
    isLive = true,
    currentCommand,
    currentCwd = "/home/ubuntu",
    onClear,
    onSendCommand,
    className,
}: ComputerTerminalViewProps) {
    const scrollRef = useRef<HTMLDivElement>(null);
    const bottomRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);
    const [wordWrap, setWordWrap] = useState(true);
    const [inputValue, setInputValue] = useState("");
    const [commandHistory, setCommandHistory] = useState<string[]>([]);
    const [historyIndex, setHistoryIndex] = useState(-1);
    const t = useTranslations("computer");

    // Auto-scroll to bottom when new lines are added (only when live)
    useEffect(() => {
        if (isLive && bottomRef.current) {
            bottomRef.current.scrollIntoView({ behavior: "smooth" });
        }
    }, [lines.length, isLive]);

    // Handle keyboard input for the terminal input
    const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === "Enter" && inputValue.trim() && onSendCommand) {
            e.preventDefault();
            onSendCommand(inputValue.trim());
            setCommandHistory((prev) => {
                const next = [inputValue.trim(), ...prev];
                return next.slice(0, 50);
            });
            setInputValue("");
            setHistoryIndex(-1);
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            if (commandHistory.length > 0) {
                const nextIndex = Math.min(historyIndex + 1, commandHistory.length - 1);
                setHistoryIndex(nextIndex);
                setInputValue(commandHistory[nextIndex]);
            }
        } else if (e.key === "ArrowDown") {
            e.preventDefault();
            if (historyIndex > 0) {
                const nextIndex = historyIndex - 1;
                setHistoryIndex(nextIndex);
                setInputValue(commandHistory[nextIndex]);
            } else {
                setHistoryIndex(-1);
                setInputValue("");
            }
        }
    }, [inputValue, onSendCommand, commandHistory, historyIndex]);

    // Lines are already filtered by the parent panel based on timeline position
    const visibleLines = !isLive
            ? lines
            : lines;

    // Shorten cwd for display (replace /home/ubuntu with ~)
    const displayCwd = currentCwd.replace(/^\/home\/ubuntu/, "~") || "~";

    return (
        <div className={cn("flex flex-col flex-1 bg-terminal-bg", className)}>
            {/* Terminal header bar */}
            <div
                className={cn(
                    "flex items-center justify-between px-3 h-8 shrink-0",
                    "border-b border-border"
                )}
            >
                <div className="flex items-center gap-2 min-w-0">
                    <TerminalSquare className="w-3.5 h-3.5 text-terminal-output/60 shrink-0" />
                    <span className="text-xs font-mono text-terminal-output/60 truncate">
                        ubuntu@sandbox:{displayCwd}
                    </span>
                </div>
                <div className="flex items-center gap-0.5 shrink-0">
                    <TooltipProvider delayDuration={300}>
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <button
                                    onClick={() => setWordWrap((v) => !v)}
                                    className={cn(
                                        "p-1 rounded transition-colors",
                                        "text-terminal-output/50 hover:text-terminal-fg hover:bg-accent",
                                        wordWrap && "text-terminal-fg bg-accent"
                                    )}
                                    aria-label={t("wordWrap")}
                                >
                                    <WrapText className="w-3.5 h-3.5" />
                                </button>
                            </TooltipTrigger>
                            <TooltipContent side="bottom">
                                {t("wordWrap")}
                            </TooltipContent>
                        </Tooltip>
                    </TooltipProvider>

                    {onClear && (
                        <TooltipProvider delayDuration={300}>
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <button
                                        onClick={onClear}
                                        className={cn(
                                            "p-1 rounded transition-colors",
                                            "text-terminal-output/50 hover:text-terminal-fg hover:bg-accent"
                                        )}
                                        aria-label={t("clearTerminal")}
                                    >
                                        <Trash2 className="w-3.5 h-3.5" />
                                    </button>
                                </TooltipTrigger>
                                <TooltipContent side="bottom">
                                    {t("clearTerminal")}
                                </TooltipContent>
                            </Tooltip>
                        </TooltipProvider>
                    )}
                </div>
            </div>

            {/* Terminal content */}
            <ScrollArea className="flex-1">
                <div
                    ref={scrollRef}
                    className="p-3 font-mono text-sm leading-relaxed min-h-full"
                    role="log"
                    aria-live="polite"
                    aria-label={t("terminalOutput")}
                >
                    {visibleLines.length === 0 && !currentCommand ? (
                        <div className="flex flex-col items-center justify-center h-full min-h-[120px] gap-2">
                            <TerminalSquare className="w-8 h-8 text-terminal-output/20" />
                            <span className="text-terminal-output/40 text-xs">
                                {t("noTerminalOutput")}
                            </span>
                        </div>
                    ) : (
                        visibleLines.map((line) => (
                            <div
                                key={line.id}
                                className="py-0.5 hover:bg-accent/50 transition-colors rounded px-1 -mx-1"
                            >
                                <TerminalLineContent
                                    line={line}
                                    wordWrap={wordWrap}
                                />
                            </div>
                        ))
                    )}

                    {/* Running command indicator */}
                    {isLive && currentCommand && (
                        <div className="py-0.5 px-1 -mx-1 group flex items-start justify-between gap-2">
                            <div className="flex items-start min-w-0">
                                <TerminalPrompt cwd={currentCwd} />
                                <span className="text-terminal-command">
                                    {currentCommand}
                                </span>
                                <Loader2 className="w-3.5 h-3.5 text-terminal-output/60 animate-spin ml-2 mt-0.5 shrink-0" />
                            </div>
                        </div>
                    )}

                    {/* Idle cursor when live and no command running */}
                    {isLive && !currentCommand && visibleLines.length > 0 && (
                        <div className="py-0.5 px-1 -mx-1 flex items-center">
                            <TerminalPrompt cwd={currentCwd} />
                            <span className="w-2 h-4 bg-terminal-fg/70 animate-pulse ml-0.5" />
                        </div>
                    )}

                    {/* Scroll anchor */}
                    <div ref={bottomRef} />
                </div>
            </ScrollArea>

            {/* Terminal input */}
            {isLive && onSendCommand && (
                <div className="flex items-center border-t border-border/50 bg-terminal-bg px-3 py-1.5 shrink-0">
                    <span className="text-terminal-prompt text-xs mr-2 flex-shrink-0 font-mono">
                        ubuntu@sandbox:{displayCwd}$
                    </span>
                    <input
                        ref={inputRef}
                        value={inputValue}
                        onChange={(e) => setInputValue(e.target.value)}
                        onKeyDown={handleKeyDown}
                        className="flex-1 bg-transparent text-terminal-fg text-xs outline-none caret-terminal-fg font-mono placeholder:text-terminal-output/30"
                        placeholder={t("typeCommand")}
                        autoFocus
                    />
                </div>
            )}
        </div>
    );
}
