"use client";

import React, { useState, useMemo } from "react";
import { Monitor, X, Maximize2, Minimize2, ExternalLink } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

export interface ComputerStreamInfo {
    streamUrl: string;
    sandboxId: string;
    authKey?: string;
}

type ViewerSize = "small" | "medium" | "large";

// E2B Desktop default resolution is 1024x768 (4:3 aspect ratio)
const E2B_RESOLUTION = { width: 1024, height: 768 };
const ASPECT_RATIO = E2B_RESOLUTION.width / E2B_RESOLUTION.height; // ~1.33

const SIZE_CONFIG: Record<ViewerSize, { width: number; height: number }> = {
    small: { width: 384, height: 288 },   // 384/288 = 1.33
    medium: { width: 512, height: 384 },  // 512/384 = 1.33
    large: { width: 640, height: 480 },   // 640/480 = 1.33
};

interface ComputerViewerProps {
    stream: ComputerStreamInfo;
    onClose?: () => void;
    className?: string;
    defaultExpanded?: boolean;
    collapsible?: boolean;
    showHeader?: boolean;
    size?: ViewerSize;
}

export function ComputerViewer({
    stream,
    onClose,
    className,
    defaultExpanded = true,
    collapsible = true,
    showHeader = true,
    size = "large",
}: ComputerViewerProps) {
    const t = useTranslations("sidebar.progress");
    const [isExpanded, setIsExpanded] = useState(defaultExpanded);
    const [isFullscreen, setIsFullscreen] = useState(false);
    const sizeConfig = SIZE_CONFIG[size];

    // Construct stream URL with auth key if provided
    const streamUrl = useMemo(() => {
        const baseUrl = stream.streamUrl;
        const authKey = stream.authKey;

        if (authKey && !baseUrl.includes('authKey=')) {
            const separator = baseUrl.includes('?') ? '&' : '?';
            return `${baseUrl}${separator}authKey=${encodeURIComponent(authKey)}`;
        }
        return baseUrl;
    }, [stream.streamUrl, stream.authKey]);

    const handleOpenExternal = () => {
        window.open(streamUrl, '_blank', 'noopener,noreferrer');
    };

    if (isFullscreen) {
        return (
            <div className="fixed inset-0 z-[100] bg-black flex flex-col">
                {/* Fullscreen header */}
                <div className="flex items-center justify-between px-4 h-12 bg-black/80 border-b border-white/10">
                    <div className="flex items-center gap-3">
                        <Monitor className="w-4 h-4 text-white" />
                        <span className="text-sm font-medium text-white">
                            {t("liveBrowser")}
                        </span>
                        <span className="text-xs text-white/60">
                            {stream.sandboxId.slice(0, 8)}...
                        </span>
                    </div>
                    <div className="flex items-center gap-1">
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-white hover:bg-white/10"
                            onClick={handleOpenExternal}
                            title="Open in new tab"
                        >
                            <ExternalLink className="w-4 h-4" />
                        </Button>
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-white hover:bg-white/10"
                            onClick={() => setIsFullscreen(false)}
                            title="Exit fullscreen"
                        >
                            <Minimize2 className="w-4 h-4" />
                        </Button>
                        {onClose && (
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8 text-white hover:bg-white/10"
                                onClick={onClose}
                                title="Close"
                            >
                                <X className="w-4 h-4" />
                            </Button>
                        )}
                    </div>
                </div>

                {/* Fullscreen iframe */}
                <div className="flex-1">
                    <iframe
                        src={streamUrl}
                        className="w-full h-full border-0"
                        allow="autoplay; fullscreen"
                        referrerPolicy="no-referrer"
                    />
                </div>
            </div>
        );
    }

    return (
        <div className={cn("border-b border-border/30", className)}>
            {/* Header */}
            {showHeader && (
                <div className="flex items-center justify-between px-3 h-9 shrink-0">
                    <div className="flex items-center gap-2 min-w-0">
                        <div className="relative">
                            <Monitor className="w-3.5 h-3.5 text-foreground flex-shrink-0" />
                            {/* Live indicator */}
                            <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse" />
                        </div>
                        <span className="text-xs font-medium truncate">
                            {t("liveBrowser")}
                        </span>
                        <span className="text-xs text-muted-foreground/60">
                            {stream.sandboxId.slice(0, 6)}...
                        </span>
                    </div>
                    <div className="flex items-center shrink-0">
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7"
                            onClick={handleOpenExternal}
                            title="Open in new tab"
                        >
                            <ExternalLink className="w-3.5 h-3.5" />
                        </Button>
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7"
                            onClick={() => setIsFullscreen(true)}
                            title="Fullscreen"
                        >
                            <Maximize2 className="w-3.5 h-3.5" />
                        </Button>
                        {collapsible && (
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7"
                                onClick={() => setIsExpanded(!isExpanded)}
                                title={isExpanded ? "Collapse" : "Expand"}
                            >
                                {isExpanded ? (
                                    <Minimize2 className="w-3.5 h-3.5" />
                                ) : (
                                    <Maximize2 className="w-3.5 h-3.5" />
                                )}
                            </Button>
                        )}
                        {onClose && (
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7"
                                onClick={onClose}
                                title="Close"
                            >
                                <X className="w-3.5 h-3.5" />
                            </Button>
                        )}
                    </div>
                </div>
            )}

            {/* Stream iframe - maintains E2B desktop aspect ratio (4:3) */}
            {isExpanded && (
                <div className="px-2 pb-2">
                    <div
                        className="rounded-md overflow-hidden border border-border bg-black mx-auto"
                        style={{
                            width: '100%',
                            maxWidth: `${sizeConfig.width}px`,
                            aspectRatio: `${E2B_RESOLUTION.width} / ${E2B_RESOLUTION.height}`,
                        }}
                    >
                        <iframe
                            src={streamUrl}
                            className="w-full h-full border-0"
                            style={{
                                display: 'block',
                            }}
                            allow="autoplay; fullscreen"
                            referrerPolicy="no-referrer"
                        />
                    </div>
                </div>
            )}
        </div>
    );
}
