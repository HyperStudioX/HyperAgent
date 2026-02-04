"use client";

import React from "react";
import { Monitor } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { useComputerStore } from "@/lib/stores/computer-store";
import { useAgentProgressStore } from "@/lib/stores/agent-progress-store";

interface ComputerToggleButtonProps {
    className?: string;
}

export function ComputerToggleButton({ className }: ComputerToggleButtonProps) {
    const t = useTranslations("computer");
    const { isOpen, togglePanel, terminalLines, browserStream } = useComputerStore();
    const { activeProgress } = useAgentProgressStore();

    // Show activity indicator if there's terminal activity or browser stream
    const hasActivity = terminalLines.length > 0 || browserStream !== null || activeProgress?.browserStream !== null;
    const isStreaming = activeProgress?.isStreaming;

    return (
        <Button
            variant="ghost"
            size="icon"
            onClick={togglePanel}
            className={cn(
                "h-9 w-9 relative",
                isOpen && "bg-secondary",
                className
            )}
            title={t("title")}
        >
            <Monitor className="w-4 h-4" />

            {/* Activity indicator */}
            {hasActivity && (
                <span
                    className={cn(
                        "absolute top-1 right-1 w-2 h-2 rounded-full",
                        isStreaming
                            ? "bg-green-500 animate-pulse"
                            : "bg-muted-foreground/50"
                    )}
                />
            )}
        </Button>
    );
}
