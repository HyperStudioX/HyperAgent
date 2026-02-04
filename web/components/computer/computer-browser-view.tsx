"use client";

import React from "react";
import { Monitor } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { ComputerViewer, type ComputerStreamInfo } from "@/components/ui/computer-viewer";

interface ComputerBrowserViewProps {
    stream: ComputerStreamInfo | null;
    onStreamClose?: () => void;
    className?: string;
}

export function ComputerBrowserView({
    stream,
    onStreamClose,
    className,
}: ComputerBrowserViewProps) {
    const t = useTranslations("computer");

    if (!stream) {
        return (
            <div className={cn(
                "flex-1 flex flex-col items-center justify-center gap-3",
                "bg-secondary/30 text-muted-foreground",
                className
            )}>
                <Monitor className="w-12 h-12 text-muted-foreground/40" />
                <div className="text-center">
                    <p className="text-sm font-medium">{t("noBrowserStream")}</p>
                    <p className="text-xs text-muted-foreground/60 mt-1">
                        {t("browserStreamWillAppear")}
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className={cn("flex-1 overflow-hidden", className)}>
            <ComputerViewer
                stream={stream}
                onClose={onStreamClose}
                showHeader={false}
                collapsible={false}
                defaultExpanded={true}
            />
        </div>
    );
}
