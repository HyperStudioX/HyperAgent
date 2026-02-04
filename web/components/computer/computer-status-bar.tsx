"use client";

import React from "react";
import { TerminalSquare, Monitor, Folder, Loader2, ListTodo } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import type { ComputerMode } from "@/lib/stores/computer-store";

interface ComputerStatusBarProps {
    activeMode: ComputerMode;
    currentCommand: string | null;
    isActive?: boolean;
}

const modeIcons: Record<ComputerMode, React.ElementType> = {
    terminal: TerminalSquare,
    plan: ListTodo,
    browser: Monitor,
    file: Folder,
};

const statusKeys: Record<ComputerMode, string> = {
    terminal: "usingTerminal",
    plan: "usingPlan",
    browser: "usingBrowser",
    file: "usingFiles",
};

export function ComputerStatusBar({
    activeMode,
    currentCommand,
    isActive = false
}: ComputerStatusBarProps) {
    const t = useTranslations("computer");
    const Icon = modeIcons[activeMode];

    return (
        <div className={cn(
            "flex items-center justify-between px-4 h-9 shrink-0",
            "bg-secondary/50 border-b border-border/30"
        )}>
            {/* Status indicator */}
            <div className="flex items-center gap-2 min-w-0">
                <div className="relative flex-shrink-0">
                    <Icon className="w-3.5 h-3.5 text-muted-foreground" />
                    {isActive && (
                        <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse" />
                    )}
                </div>
                <span className="text-xs text-muted-foreground truncate">
                    {t(statusKeys[activeMode])}
                </span>
                {isActive && (
                    <Loader2 className="w-3 h-3 text-muted-foreground animate-spin flex-shrink-0" />
                )}
            </div>

            {/* Current command (if terminal mode) */}
            {currentCommand && activeMode === "terminal" && (
                <div className="flex items-center gap-1.5 min-w-0 ml-3">
                    <span className="text-xs text-muted-foreground/60">$</span>
                    <span className="text-xs font-mono text-muted-foreground truncate max-w-[200px]">
                        {currentCommand}
                    </span>
                </div>
            )}
        </div>
    );
}
