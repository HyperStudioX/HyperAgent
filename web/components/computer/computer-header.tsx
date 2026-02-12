"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { TerminalSquare, Monitor, Folder, X, ListTodo, Circle, Settings2, Eye, EyeOff, PanelRightOpen } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import type { ComputerMode } from "@/lib/stores/computer-store";

interface ComputerHeaderProps {
    activeMode: ComputerMode;
    onModeChange: (mode: ComputerMode) => void;
    onClose: () => void;
    sandboxStatus?: "connected" | "disconnected" | "connecting";
    tabActivity?: Partial<Record<ComputerMode, boolean>>;
    followAgent?: boolean;
    autoOpen?: boolean;
    onFollowAgentChange?: (enabled: boolean) => void;
    onAutoOpenChange?: (enabled: boolean) => void;
}

const modeConfig: { mode: ComputerMode; icon: React.ElementType; labelKey: string }[] = [
    { mode: "plan", icon: ListTodo, labelKey: "plan" },
    { mode: "terminal", icon: TerminalSquare, labelKey: "terminal" },
    { mode: "browser", icon: Monitor, labelKey: "browser" },
    { mode: "file", icon: Folder, labelKey: "files" },
];

export function ComputerHeader({
    activeMode,
    onModeChange,
    onClose,
    sandboxStatus = "connected",
    tabActivity = {},
    followAgent = true,
    autoOpen = true,
    onFollowAgentChange,
    onAutoOpenChange,
}: ComputerHeaderProps) {
    const t = useTranslations("computer");
    const [showSettings, setShowSettings] = useState(false);
    const settingsRef = useRef<HTMLDivElement>(null);
    const tabListRef = useRef<HTMLDivElement>(null);

    // Close settings dropdown when clicking outside
    useEffect(() => {
        if (!showSettings) return;
        const handleClickOutside = (e: MouseEvent) => {
            if (settingsRef.current && !settingsRef.current.contains(e.target as Node)) {
                setShowSettings(false);
            }
        };
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, [showSettings]);

    // Arrow key navigation for tab buttons
    const handleTabKeyDown = useCallback((e: React.KeyboardEvent<HTMLDivElement>) => {
        const currentIndex = modeConfig.findIndex(({ mode }) => mode === activeMode);
        let nextIndex: number | null = null;

        if (e.key === "ArrowRight" || e.key === "ArrowDown") {
            e.preventDefault();
            nextIndex = (currentIndex + 1) % modeConfig.length;
        } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
            e.preventDefault();
            nextIndex = (currentIndex - 1 + modeConfig.length) % modeConfig.length;
        } else if (e.key === "Home") {
            e.preventDefault();
            nextIndex = 0;
        } else if (e.key === "End") {
            e.preventDefault();
            nextIndex = modeConfig.length - 1;
        }

        if (nextIndex !== null) {
            onModeChange(modeConfig[nextIndex].mode);
            // Focus the newly selected tab
            const buttons = tabListRef.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]');
            buttons?.[nextIndex]?.focus();
        }
    }, [activeMode, onModeChange]);

    return (
        <div className="flex flex-col shrink-0">
            {/* Top row: title + connection status + close */}
            <div className="flex items-center justify-between px-4 h-11 border-b border-border/50">
                <div className="flex items-center gap-2">
                    {/* Connection status indicator - semantic status colors intentionally not using theme tokens */}
                    <Circle
                        className={cn(
                            "w-2 h-2 flex-shrink-0",
                            sandboxStatus === "connected" && "fill-green-500 text-green-500",
                            sandboxStatus === "connecting" && "fill-amber-500 text-amber-500 animate-pulse",
                            sandboxStatus === "disconnected" && "fill-muted-foreground/40 text-muted-foreground/40"
                        )}
                    />
                    <span className="text-sm font-medium text-foreground">
                        {t("panelTitle")}
                    </span>
                </div>

                <div className="flex items-center gap-0.5">
                    {/* Settings button */}
                    <div className="relative" ref={settingsRef}>
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 text-muted-foreground hover:text-foreground"
                            onClick={() => setShowSettings(!showSettings)}
                            title={t("settings")}
                            aria-label={t("settings")}
                            aria-expanded={showSettings}
                            aria-haspopup="true"
                        >
                            <Settings2 className="w-3.5 h-3.5" />
                        </Button>

                        {/* Settings dropdown */}
                        {showSettings && (
                            <div className="absolute right-0 top-full mt-1 w-52 bg-background border border-border/50 rounded-md py-1 z-50">
                                {/* Follow Agent toggle */}
                                <button
                                    className="flex items-center gap-2.5 w-full px-3 py-2 text-xs hover:bg-muted/50 transition-colors"
                                    onClick={() => onFollowAgentChange?.(!followAgent)}
                                >
                                    {followAgent ? (
                                        <Eye className="w-3.5 h-3.5 text-foreground" />
                                    ) : (
                                        <EyeOff className="w-3.5 h-3.5 text-muted-foreground" />
                                    )}
                                    <span className="flex-1 text-left text-foreground">
                                        {t("followAgent")}
                                    </span>
                                    {/* Semantic on/off status colors */}
                                    <span className={cn(
                                        "text-[10px] px-1.5 py-0.5 rounded font-medium",
                                        followAgent
                                            ? "bg-green-500/15 text-green-600 dark:text-green-400"
                                            : "bg-muted text-muted-foreground"
                                    )}>
                                        {followAgent ? t("on") : t("off")}
                                    </span>
                                </button>

                                {/* Auto-open toggle */}
                                <button
                                    className="flex items-center gap-2.5 w-full px-3 py-2 text-xs hover:bg-muted/50 transition-colors"
                                    onClick={() => onAutoOpenChange?.(!autoOpen)}
                                >
                                    <PanelRightOpen className="w-3.5 h-3.5 text-muted-foreground" />
                                    <span className="flex-1 text-left text-foreground">
                                        {t("autoOpen")}
                                    </span>
                                    {/* Semantic on/off status colors */}
                                    <span className={cn(
                                        "text-[10px] px-1.5 py-0.5 rounded font-medium",
                                        autoOpen
                                            ? "bg-green-500/15 text-green-600 dark:text-green-400"
                                            : "bg-muted text-muted-foreground"
                                    )}>
                                        {autoOpen ? t("on") : t("off")}
                                    </span>
                                </button>
                            </div>
                        )}
                    </div>

                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-muted-foreground hover:text-foreground"
                        onClick={onClose}
                        title={t("close")}
                        aria-label={t("close")}
                    >
                        <X className="w-3.5 h-3.5" />
                    </Button>
                </div>
            </div>

            {/* Tab row: icon+label buttons */}
            <div
                className="flex items-center px-2 h-10 border-b border-border/30 gap-0.5"
                role="tablist"
                aria-label={t("panelTitle")}
                ref={tabListRef}
                onKeyDown={handleTabKeyDown}
            >
                {modeConfig.map(({ mode, icon: Icon, labelKey }) => {
                    const isActive = activeMode === mode;
                    const hasActivity = !isActive && tabActivity[mode];

                    return (
                        <button
                            key={mode}
                            className={cn(
                                "relative flex items-center gap-1.5 px-3 h-7 rounded-md text-xs font-medium transition-colors",
                                isActive
                                    ? "bg-secondary text-foreground"
                                    : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
                            )}
                            onClick={() => onModeChange(mode)}
                            role="tab"
                            aria-selected={isActive}
                            tabIndex={isActive ? 0 : -1}
                        >
                            <Icon className="w-3.5 h-3.5 flex-shrink-0" />
                            <span>{t(labelKey)}</span>

                            {/* Activity dot */}
                            {hasActivity && (
                                <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-primary" />
                            )}
                        </button>
                    );
                })}
            </div>
        </div>
    );
}
