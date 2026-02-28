"use client";

import React, { useState, useCallback, useRef } from "react";
import {
    Monitor,
    Globe,
    ArrowLeft,
    ArrowRight,
    RotateCw,
    Maximize2,
    Minimize2,
    ExternalLink,
    Lock,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { useComputerStore } from "@/lib/stores/computer-store";
import type { ComputerStreamInfo } from "@/lib/stores/agent-progress-store";
import { Button } from "@/components/ui/button";

interface ComputerBrowserViewProps {
    stream: ComputerStreamInfo | null;
    className?: string;
}

export function ComputerBrowserView({
    stream,
    className,
}: ComputerBrowserViewProps) {
    const t = useTranslations("computer");

    // Browser state from store - access underlying state directly for proper Zustand tracking
    // (calling getter methods like getBrowserUrl() inside selectors doesn't subscribe to state changes)
    const browserUrl = useComputerStore((state) => {
        const id = state.activeConversationId;
        return id ? state.conversationStates[id]?.browserUrl ?? null : null;
    });
    const browserAction = useComputerStore((state) => {
        const id = state.activeConversationId;
        return id ? state.conversationStates[id]?.browserAction ?? null : null;
    });
    const browserIsNavigating = useComputerStore((state) => {
        const id = state.activeConversationId;
        return id ? state.conversationStates[id]?.browserIsNavigating ?? false : false;
    });
    const isLive = useComputerStore((state) => {
        const id = state.activeConversationId;
        return id ? state.conversationStates[id]?.isLive ?? true : true;
    });

    const [isFullscreen, setIsFullscreen] = useState(false);
    const iframeRef = useRef<HTMLIFrameElement>(null);

    // Show overlay when action is running
    const visibleAction = browserAction?.status === "running" ? browserAction : null;

    // Send auth key to iframe via postMessage after load.
    // We use "*" as targetOrigin because the iframe sandbox omits allow-same-origin,
    // giving the iframe an opaque (null) origin that cannot be matched by a specific origin string.
    const handleIframeLoad = useCallback(
        (ref: React.RefObject<HTMLIFrameElement | null>) => {
            if (stream?.authKey && ref.current?.contentWindow) {
                ref.current.contentWindow.postMessage(
                    { type: "auth", authKey: stream.authKey },
                    "*"
                );
            }
        },
        [stream]
    );

    const handleScreenshot = useCallback(() => {
        if (stream?.streamUrl) {
            window.open(stream.streamUrl, '_blank', 'noopener,noreferrer');
        }
    }, [stream]);

    // Extract display URL (truncated for the address bar)
    const displayUrl = browserUrl || "";
    const isHttps = displayUrl.startsWith("https://");

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

    // Action overlay toast
    const actionOverlay = visibleAction ? (
        <div className="absolute bottom-3 left-1/2 -translate-x-1/2 z-10 max-w-[80%]">
            <div className={cn(
                "flex items-center gap-2 px-3 py-1.5 rounded-lg",
                "bg-background/95 border border-border/50 shadow-sm",
                "animate-in fade-in slide-in-from-bottom-2 duration-200"
            )}>
                <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse flex-shrink-0" />
                <span className="text-xs text-foreground truncate">
                    {visibleAction.description}
                </span>
            </div>
        </div>
    ) : null;

    // Use a single container with CSS-based fullscreen toggle to avoid
    // destroying/recreating the iframe (which loses iframe state and causes reloads).
    return (
        <div className={cn(
            "flex flex-col overflow-hidden",
            isFullscreen
                ? "fixed inset-0 z-[100] bg-background"
                : "flex-1",
            className
        )}>
            {/* Browser chrome - adapts styling based on fullscreen state */}
            <div className={cn(
                "flex items-center gap-1.5 px-2 py-1.5 border-b",
                isFullscreen
                    ? "px-3 bg-card/95 backdrop-blur-sm border-border"
                    : "bg-secondary/50 border-border/30"
            )}>
                {/* Navigation buttons */}
                <Button
                    variant="ghost"
                    size="icon"
                    className={cn("h-6 w-6 cursor-default", isFullscreen ? "text-muted-foreground/60" : "text-muted-foreground/50")}
                    disabled
                    title={t("browserBack")}
                >
                    <ArrowLeft className="w-3.5 h-3.5" />
                </Button>
                <Button
                    variant="ghost"
                    size="icon"
                    className={cn("h-6 w-6 cursor-default", isFullscreen ? "text-muted-foreground/60" : "text-muted-foreground/50")}
                    disabled
                    title={t("browserForward")}
                >
                    <ArrowRight className="w-3.5 h-3.5" />
                </Button>
                <Button
                    variant="ghost"
                    size="icon"
                    className={cn(
                        "h-6 w-6 cursor-default",
                        isFullscreen ? "text-muted-foreground/60" : "text-muted-foreground/50",
                        browserIsNavigating && "animate-spin"
                    )}
                    disabled
                    title={t("browserRefresh")}
                >
                    <RotateCw className="w-3.5 h-3.5" />
                </Button>

                {/* URL bar */}
                <div className={cn(
                    "flex-1 flex items-center gap-1.5 h-7 px-2.5 rounded-md min-w-0",
                    isFullscreen
                        ? "bg-accent/50 border border-border"
                        : "bg-background/80 border border-border/40"
                )}>
                    {displayUrl ? (
                        <>
                            {isHttps ? (
                                <Lock className={cn("w-3 h-3 flex-shrink-0", isFullscreen ? "text-muted-foreground/60" : "text-muted-foreground/60")} />
                            ) : (
                                <Globe className={cn("w-3 h-3 flex-shrink-0", isFullscreen ? "text-muted-foreground/60" : "text-muted-foreground/60")} />
                            )}
                            <span className={cn("text-xs truncate", isFullscreen ? "text-muted-foreground" : "text-muted-foreground select-all")}>
                                {displayUrl}
                            </span>
                        </>
                    ) : (
                        <>
                            <Globe className={cn("w-3 h-3 flex-shrink-0", isFullscreen ? "text-muted-foreground/40" : "text-muted-foreground/40")} />
                            <span className={cn("text-xs truncate", isFullscreen ? "text-muted-foreground/40" : "text-muted-foreground/40")}>
                                {t("browserUrlPlaceholder")}
                            </span>
                        </>
                    )}
                </div>

                {/* Right-side controls */}
                {/* Semantic live status color - intentionally green */}
                {isLive && stream && (
                    <div className={cn(
                        "flex items-center gap-0.5 px-1.5 py-0.5 rounded-full",
                        isFullscreen ? "bg-green-500/20" : "bg-green-500/10 border border-green-500/20"
                    )}>
                        <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                        <span className={cn(
                            "text-[10px] font-medium",
                            isFullscreen ? "text-green-400" : "text-green-600 dark:text-green-400"
                        )}>
                            {t("browserLive")}
                        </span>
                    </div>
                )}

                <Button
                    variant="ghost"
                    size="icon"
                    className={cn("h-6 w-6", isFullscreen && "text-foreground hover:bg-accent")}
                    onClick={handleScreenshot}
                    title={t("openInNewTab")}
                    aria-label={t("openInNewTab")}
                >
                    <ExternalLink className="w-3.5 h-3.5" />
                </Button>
                <Button
                    variant="ghost"
                    size="icon"
                    className={cn("h-6 w-6", isFullscreen && "text-foreground hover:bg-accent")}
                    onClick={() => setIsFullscreen(!isFullscreen)}
                    title={isFullscreen ? t("browserExitFullscreen") : t("browserFullscreen")}
                    aria-label={isFullscreen ? t("browserExitFullscreen") : t("browserFullscreen")}
                >
                    {isFullscreen ? (
                        <Minimize2 className="w-3.5 h-3.5" />
                    ) : (
                        <Maximize2 className="w-3.5 h-3.5" />
                    )}
                </Button>
            </div>

            {/* Loading progress bar */}
            {browserIsNavigating && (
                <div className={cn("h-0.5 w-full overflow-hidden", isFullscreen ? "bg-accent/50" : "bg-secondary/30")}>
                    <div className="h-full bg-primary/70 animate-progress-indeterminate" />
                </div>
            )}

            {/* Single iframe area - preserved across fullscreen toggle */}
            <div className="flex-1 relative bg-muted">
                <iframe
                    ref={iframeRef}
                    src={stream.streamUrl}
                    className="w-full h-full border-0"
                    style={{ display: "block" }}
                    sandbox="allow-scripts allow-popups allow-pointer-lock"
                    allow="autoplay; fullscreen"
                    referrerPolicy="no-referrer"
                    onLoad={() => handleIframeLoad(iframeRef)}
                    title={t("browserIframeTitle")}
                />
                {actionOverlay}
            </div>
        </div>
    );
}
