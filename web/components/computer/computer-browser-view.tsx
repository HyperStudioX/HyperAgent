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
    Camera,
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

    // Browser state from store
    const browserUrl = useComputerStore((state) => state.getBrowserUrl());
    const browserAction = useComputerStore((state) => state.getBrowserAction());
    const browserIsNavigating = useComputerStore((state) => state.getBrowserIsNavigating());
    const isLive = useComputerStore((state) => state.getIsLive());

    const [isFullscreen, setIsFullscreen] = useState(false);
    const iframeRef = useRef<HTMLIFrameElement>(null);
    const fullscreenIframeRef = useRef<HTMLIFrameElement>(null);

    // Show overlay when action is running
    const visibleAction = browserAction?.status === "running" ? browserAction : null;

    // Send auth key to iframe via postMessage after load
    const handleIframeLoad = useCallback(
        (ref: React.RefObject<HTMLIFrameElement | null>) => {
            if (stream?.authKey && ref.current?.contentWindow) {
                try {
                    const targetOrigin = new URL(stream.streamUrl).origin;
                    ref.current.contentWindow.postMessage(
                        { type: "auth", authKey: stream.authKey },
                        targetOrigin
                    );
                } catch {
                    // URL parsing failed
                }
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

    const browserChrome = (
        <div className="flex items-center gap-1.5 px-2 py-1.5 bg-secondary/50 border-b border-border/30">
            {/* Navigation buttons */}
            <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 text-muted-foreground/50 cursor-default"
                disabled
                title={t("browserBack")}
            >
                <ArrowLeft className="w-3.5 h-3.5" />
            </Button>
            <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 text-muted-foreground/50 cursor-default"
                disabled
                title={t("browserForward")}
            >
                <ArrowRight className="w-3.5 h-3.5" />
            </Button>
            <Button
                variant="ghost"
                size="icon"
                className={cn(
                    "h-6 w-6 text-muted-foreground/50 cursor-default",
                    browserIsNavigating && "animate-spin"
                )}
                disabled
                title={t("browserRefresh")}
            >
                <RotateCw className="w-3 h-3" />
            </Button>

            {/* URL bar */}
            <div className="flex-1 flex items-center gap-1.5 h-7 px-2.5 rounded-md bg-background/80 border border-border/40 min-w-0">
                {displayUrl ? (
                    <>
                        {isHttps ? (
                            <Lock className="w-3 h-3 text-muted-foreground/60 flex-shrink-0" />
                        ) : (
                            <Globe className="w-3 h-3 text-muted-foreground/60 flex-shrink-0" />
                        )}
                        <span className="text-xs text-muted-foreground truncate select-all">
                            {displayUrl}
                        </span>
                    </>
                ) : (
                    <>
                        <Globe className="w-3 h-3 text-muted-foreground/40 flex-shrink-0" />
                        <span className="text-xs text-muted-foreground/40 truncate">
                            {t("browserUrlPlaceholder")}
                        </span>
                    </>
                )}
            </div>

            {/* Right-side controls */}
            {isLive && stream && (
                <div className="flex items-center gap-0.5 px-1.5 py-0.5 rounded-full bg-green-500/10 border border-green-500/20">
                    <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                    <span className="text-[10px] font-medium text-green-600 dark:text-green-400">
                        {t("browserLive")}
                    </span>
                </div>
            )}

            <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={handleScreenshot}
                title={t("browserScreenshot")}
            >
                <Camera className="w-3.5 h-3.5" />
            </Button>
            <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={() => setIsFullscreen(!isFullscreen)}
                title={isFullscreen ? t("browserExitFullscreen") : t("browserFullscreen")}
            >
                {isFullscreen ? (
                    <Minimize2 className="w-3.5 h-3.5" />
                ) : (
                    <Maximize2 className="w-3.5 h-3.5" />
                )}
            </Button>
        </div>
    );

    // Loading progress bar
    const progressBar = browserIsNavigating ? (
        <div className="h-0.5 w-full bg-secondary/30 overflow-hidden">
            <div className="h-full bg-primary/70 animate-progress-indeterminate" />
        </div>
    ) : null;

    // Action overlay toast
    const actionOverlay = visibleAction ? (
        <div className="absolute bottom-3 left-1/2 -translate-x-1/2 z-10 max-w-[80%]">
            <div className={cn(
                "flex items-center gap-2 px-3 py-1.5 rounded-lg",
                "bg-background/80 backdrop-blur-sm border border-border/50 shadow-sm",
                "animate-in fade-in slide-in-from-bottom-2 duration-200"
            )}>
                <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse flex-shrink-0" />
                <span className="text-xs text-foreground truncate">
                    {visibleAction.description}
                </span>
            </div>
        </div>
    ) : null;

    // Fullscreen mode
    if (isFullscreen) {
        return (
            <div className="fixed inset-0 z-[100] bg-black flex flex-col">
                {/* Fullscreen browser chrome */}
                <div className="flex items-center gap-1.5 px-3 py-1.5 bg-black/80 border-b border-white/10">
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 text-white/40 cursor-default"
                        disabled
                    >
                        <ArrowLeft className="w-3.5 h-3.5" />
                    </Button>
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 text-white/40 cursor-default"
                        disabled
                    >
                        <ArrowRight className="w-3.5 h-3.5" />
                    </Button>
                    <Button
                        variant="ghost"
                        size="icon"
                        className={cn(
                            "h-6 w-6 text-white/40 cursor-default",
                            browserIsNavigating && "animate-spin"
                        )}
                        disabled
                    >
                        <RotateCw className="w-3 h-3" />
                    </Button>

                    {/* Fullscreen URL bar */}
                    <div className="flex-1 flex items-center gap-1.5 h-7 px-2.5 rounded-md bg-white/5 border border-white/10 min-w-0">
                        {displayUrl ? (
                            <>
                                {isHttps ? (
                                    <Lock className="w-3 h-3 text-white/40 flex-shrink-0" />
                                ) : (
                                    <Globe className="w-3 h-3 text-white/40 flex-shrink-0" />
                                )}
                                <span className="text-xs text-white/70 truncate">
                                    {displayUrl}
                                </span>
                            </>
                        ) : (
                            <>
                                <Globe className="w-3 h-3 text-white/30 flex-shrink-0" />
                                <span className="text-xs text-white/30 truncate">
                                    {t("browserUrlPlaceholder")}
                                </span>
                            </>
                        )}
                    </div>

                    {isLive && (
                        <div className="flex items-center gap-0.5 px-1.5 py-0.5 rounded-full bg-green-500/20">
                            <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                            <span className="text-[10px] font-medium text-green-400">
                                {t("browserLive")}
                            </span>
                        </div>
                    )}

                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 text-white hover:bg-white/10"
                        onClick={handleScreenshot}
                    >
                        <Camera className="w-3.5 h-3.5" />
                    </Button>
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 text-white hover:bg-white/10"
                        onClick={() => setIsFullscreen(false)}
                        title={t("browserExitFullscreen")}
                    >
                        <Minimize2 className="w-3.5 h-3.5" />
                    </Button>
                </div>

                {/* Fullscreen progress bar */}
                {browserIsNavigating && (
                    <div className="h-0.5 w-full bg-white/5 overflow-hidden">
                        <div className="h-full bg-primary/70 animate-progress-indeterminate" />
                    </div>
                )}

                {/* Fullscreen iframe */}
                <div className="flex-1 relative">
                    <iframe
                        ref={fullscreenIframeRef}
                        src={stream.streamUrl}
                        className="w-full h-full border-0"
                        sandbox="allow-scripts allow-same-origin allow-popups allow-pointer-lock"
                        allow="autoplay; fullscreen"
                        referrerPolicy="no-referrer"
                        onLoad={() => handleIframeLoad(fullscreenIframeRef)}
                    />
                    {actionOverlay}
                </div>
            </div>
        );
    }

    return (
        <div className={cn("flex-1 flex flex-col overflow-hidden", className)}>
            {/* Browser chrome */}
            {browserChrome}

            {/* Loading progress bar */}
            {progressBar}

            {/* Iframe area */}
            <div className="flex-1 relative bg-black">
                <iframe
                    ref={iframeRef}
                    src={stream.streamUrl}
                    className="w-full h-full border-0"
                    style={{ display: "block" }}
                    sandbox="allow-scripts allow-same-origin allow-popups allow-pointer-lock"
                    allow="autoplay; fullscreen"
                    referrerPolicy="no-referrer"
                    onLoad={() => handleIframeLoad(iframeRef)}
                />
                {actionOverlay}
            </div>
        </div>
    );
}
