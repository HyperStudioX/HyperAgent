"use client";

import React from "react";
import { TerminalSquare, Monitor, Folder, X, ListTodo } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import type { ComputerMode } from "@/lib/stores/computer-store";

interface ComputerHeaderProps {
    activeMode: ComputerMode;
    onModeChange: (mode: ComputerMode) => void;
    onClose: () => void;
}

const modeConfig: { mode: ComputerMode; icon: React.ElementType; labelKey: string }[] = [
    { mode: "terminal", icon: TerminalSquare, labelKey: "terminal" },
    { mode: "plan", icon: ListTodo, labelKey: "plan" },
    { mode: "browser", icon: Monitor, labelKey: "browser" },
    { mode: "file", icon: Folder, labelKey: "files" },
];

export function ComputerHeader({ activeMode, onModeChange, onClose }: ComputerHeaderProps) {
    const t = useTranslations("computer");

    return (
        <div className="flex items-center justify-between px-4 h-12 border-b border-border/50 shrink-0">
            {/* Title */}
            <span className="text-sm font-medium text-foreground">
                {t("title")}
            </span>

            {/* Mode buttons */}
            <div className="flex items-center gap-1">
                {modeConfig.map(({ mode, icon: Icon, labelKey }) => (
                    <Button
                        key={mode}
                        variant="ghost"
                        size="icon"
                        className={cn(
                            "h-8 w-8 transition-colors",
                            activeMode === mode
                                ? "bg-secondary text-foreground"
                                : "text-muted-foreground hover:text-foreground"
                        )}
                        onClick={() => onModeChange(mode)}
                        title={t(labelKey)}
                    >
                        <Icon className="w-4 h-4" />
                    </Button>
                ))}

                {/* Separator */}
                <div className="w-px h-4 bg-border mx-1" />

                {/* Close button */}
                <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-muted-foreground hover:text-foreground"
                    onClick={onClose}
                    title={t("close")}
                >
                    <X className="w-4 h-4" />
                </Button>
            </div>
        </div>
    );
}
