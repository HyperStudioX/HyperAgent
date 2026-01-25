"use client";

import React, { useState } from "react";
import { useTranslations } from "next-intl";
import { Download, Maximize2, X, Loader2, ImageIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface GeneratedMediaProps {
    data?: string; // Base64 image or HTML string (for immediate display)
    url?: string; // Persistent URL for loading from storage
    mimeType: "image/png" | "image/jpeg" | "image/gif" | "image/webp" | "text/html";
    className?: string;
}

export function GeneratedMedia({ data, url, mimeType, className }: GeneratedMediaProps) {
    const t = useTranslations("preview");
    const [isFullscreen, setIsFullscreen] = useState(false);
    const [isHovered, setIsHovered] = useState(false);
    const [isLoading, setIsLoading] = useState(!data && !!url);
    const [loadError, setLoadError] = useState(false);
    const [useUrlFallback, setUseUrlFallback] = useState(false);

    const isImage = mimeType.startsWith("image/");
    const imageExt = isImage ? mimeType.split("/")[1] : "png";

    // Determine the image source - prefer base64 data for immediate display, fall back to URL
    const trimmedData = data?.trim();
    const sanitizedData = trimmedData ? trimmedData.replace(/\s+/g, "") : "";
    const dataSrc = trimmedData
        ? (trimmedData.startsWith("data:") ? trimmedData : `data:${mimeType};base64,${sanitizedData}`)
        : "";
    const imageSrc = useUrlFallback && url ? url : dataSrc || url || "";

    const handleDownload = async () => {
        if (isImage) {
            const link = document.createElement("a");
            if (data) {
                // Download from base64 data
                link.href = `data:${mimeType};base64,${data}`;
            } else if (url) {
                // Download from URL
                link.href = url;
            }
            link.download = `generated-image-${Date.now()}.${imageExt}`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        } else if (mimeType === "text/html" && data) {
            const blob = new Blob([data], { type: "text/html" });
            const blobUrl = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = blobUrl;
            link.download = `chart-${Date.now()}.html`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(blobUrl);
        }
    };

    const handleImageLoad = () => {
        setIsLoading(false);
        setLoadError(false);
    };

    const handleImageError = () => {
        if (!useUrlFallback && url && dataSrc) {
            // Try falling back to URL if base64 fails
            setUseUrlFallback(true);
            setIsLoading(true);
            return;
        }
        setIsLoading(false);
        setLoadError(true);
    };

    const renderContent = () => {
        // Use span elements with block display to avoid hydration errors
        // when rendered inside markdown <p> tags (div cannot be a descendant of p)
        if (isImage) {
            if (loadError) {
                return (
                    <span className="flex flex-col items-center justify-center h-64 gap-3 text-muted-foreground">
                        <span className="flex items-center justify-center w-12 h-12 rounded-full bg-muted/50">
                            <ImageIcon className="w-5 h-5" />
                        </span>
                        <span className="text-sm font-medium">{t("failedToLoadImageSimple")}</span>
                    </span>
                );
            }
            return (
                <span className="block relative group/image">
                    {isLoading && (
                        <span className="absolute inset-0 flex items-center justify-center bg-background/80 backdrop-blur-sm rounded-xl">
                            <span className="flex flex-col items-center gap-3">
                                <Loader2 className="w-6 h-6 animate-spin text-primary" />
                                <span className="text-xs font-medium text-muted-foreground">{t("loadingImage")}</span>
                            </span>
                        </span>
                    )}
                    <img
                        src={imageSrc}
                        alt={t("generatedImageAlt")}
                        className={cn(
                            "w-full h-auto rounded-xl transition-all duration-500",
                            isLoading && "opacity-0 scale-95",
                            !isLoading && "opacity-100 scale-100"
                        )}
                        onLoad={handleImageLoad}
                        onError={handleImageError}
                    />
                </span>
            );
        } else if (mimeType === "text/html" && data) {
            return (
                <iframe
                    srcDoc={data}
                    title={t("interactiveContentTitle")}
                    className="w-full h-[500px] rounded-xl border-0"
                    sandbox="allow-scripts allow-same-origin"
                />
            );
        }
        return null;
    };

    // Don't render if we have neither data nor url
    if (!data && !url) {
        return null;
    }

    // Use span elements with block display to avoid hydration errors
    // when rendered inside markdown <p> tags (div cannot be a descendant of p)
    return (
        <>
            <span
                className={cn(
                    "block relative my-6 rounded-2xl overflow-hidden",
                    "transition-all duration-300",
                    "bg-card border-2 border-border/60",
                    "shadow-sm hover:shadow-md hover:border-border",
                    className
                )}
                onMouseEnter={() => setIsHovered(true)}
                onMouseLeave={() => setIsHovered(false)}
            >
                {/* Header with controls - cleaner, more refined */}
                <span
                    className={cn(
                        "flex items-center justify-between gap-3",
                        "px-4 md:px-5 py-3",
                        "border-b border-border/50",
                        "bg-secondary/30 backdrop-blur-sm"
                    )}
                >
                    <span className="flex items-center gap-2.5">
                        <span className="flex items-center justify-center w-5 h-5 rounded-md bg-primary/10">
                            <ImageIcon className="w-3 h-3 text-primary" />
                        </span>
                        <span className="text-xs font-semibold tracking-wide text-foreground/90">
                            {isImage ? t("generatedImageLabel") : t("interactiveChartLabel")}
                        </span>
                    </span>

                    <span className="flex items-center gap-1.5">
                        <button
                            onClick={() => setIsFullscreen(true)}
                            className={cn(
                                "flex items-center justify-center",
                                "w-8 h-8",
                                "rounded-lg",
                                "transition-all duration-200",
                                "text-muted-foreground hover:text-foreground",
                                "hover:bg-secondary/80 active:scale-95"
                            )}
                            title={t("viewFullscreen")}
                            aria-label={t("viewFullscreen")}
                        >
                            <Maximize2 className="w-4 h-4" />
                        </button>
                        <button
                            onClick={handleDownload}
                            className={cn(
                                "flex items-center justify-center",
                                "w-8 h-8",
                                "rounded-lg",
                                "transition-all duration-200",
                                "text-muted-foreground hover:text-foreground",
                                "hover:bg-secondary/80 active:scale-95"
                            )}
                            title={t("download")}
                            aria-label={t("downloadImage")}
                        >
                            <Download className="w-4 h-4" />
                        </button>
                    </span>
                </span>

                {/* Media content - generous padding, cleaner presentation */}
                <span className="block p-6 md:p-8 bg-gradient-to-b from-background/50 to-background">
                    {renderContent()}
                </span>
            </span>

            {/* Fullscreen modal - ultra-clean with smooth animations */}
            {isFullscreen && (
                <div
                    className="fixed inset-0 z-50 bg-background/98 backdrop-blur-xl animate-in fade-in duration-300"
                    onClick={() => setIsFullscreen(false)}
                >
                    <div className="container h-full max-w-7xl mx-auto p-4 md:p-8 flex flex-col animate-in slide-in-from-bottom-4 duration-400 delay-75">
                        {/* Clean header bar */}
                        <div className="flex items-center justify-between mb-6 pb-5 border-b border-border/50">
                            <div className="flex items-center gap-3">
                                <span className="flex items-center justify-center w-8 h-8 rounded-xl bg-primary/10">
                                    <ImageIcon className="w-4 h-4 text-primary" />
                                </span>
                                <h3 className="text-base font-bold tracking-tight">
                                    {isImage ? t("generatedImage") : t("interactiveChart")}
                                </h3>
                            </div>
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        handleDownload();
                                    }}
                                    className={cn(
                                        "flex items-center gap-2.5",
                                        "px-4 py-2.5",
                                        "text-sm font-semibold",
                                        "rounded-xl",
                                        "transition-all duration-200",
                                        "bg-secondary/60 hover:bg-secondary",
                                        "text-foreground",
                                        "active:scale-95"
                                    )}
                                >
                                    <Download className="w-4 h-4" />
                                    <span className="hidden sm:inline">{t("download")}</span>
                                </button>
                                <button
                                    onClick={() => setIsFullscreen(false)}
                                    className={cn(
                                        "flex items-center gap-2.5",
                                        "px-4 py-2.5",
                                        "text-sm font-semibold",
                                        "rounded-xl",
                                        "transition-all duration-200",
                                        "bg-muted hover:bg-muted/80",
                                        "text-foreground",
                                        "active:scale-95"
                                    )}
                                >
                                    <X className="w-4 h-4" />
                                    <span className="hidden sm:inline">{t("close")}</span>
                                </button>
                            </div>
                        </div>

                        {/* Content area with refined styling */}
                        <div
                            className="flex-1 overflow-auto bg-card/50 rounded-2xl border border-border/60 p-8 md:p-12 shadow-lg backdrop-blur-sm"
                            onClick={(e) => e.stopPropagation()}
                        >
                            <div className="flex items-center justify-center min-h-full">
                                {renderContent()}
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
