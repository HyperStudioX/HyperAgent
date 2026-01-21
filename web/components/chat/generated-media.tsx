"use client";

import React, { useState } from "react";
import { Download, Maximize2, X, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface GeneratedMediaProps {
    data?: string; // Base64 image or HTML string (for immediate display)
    url?: string; // Persistent URL for loading from storage
    mimeType: "image/png" | "image/jpeg" | "image/gif" | "image/webp" | "text/html";
    className?: string;
}

export function GeneratedMedia({ data, url, mimeType, className }: GeneratedMediaProps) {
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
                    <span className="flex items-center justify-center h-48 text-muted-foreground">
                        <span>Failed to load image</span>
                    </span>
                );
            }
            return (
                <span className="block relative">
                    {isLoading && (
                        <span className="absolute inset-0 flex items-center justify-center bg-secondary/50">
                            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                        </span>
                    )}
                    <img
                        src={imageSrc}
                        alt="Generated image"
                        className={cn("w-full h-auto rounded-lg", isLoading && "opacity-0")}
                        onLoad={handleImageLoad}
                        onError={handleImageError}
                    />
                </span>
            );
        } else if (mimeType === "text/html" && data) {
            return (
                <iframe
                    srcDoc={data}
                    title="Interactive content"
                    className="w-full h-[500px] rounded-lg border-0"
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
                    "block relative my-5 rounded-lg overflow-hidden",
                    "ring-1 transition-all duration-300",
                    "bg-secondary/30 ring-border",
                    isHovered && "ring-border/60",
                    className
                )}
                onMouseEnter={() => setIsHovered(true)}
                onMouseLeave={() => setIsHovered(false)}
            >
                {/* Header with controls */}
                <span
                    className={cn(
                        "flex items-center justify-between",
                        "px-3 md:px-4 py-2.5",
                        "border-b border-border",
                        "bg-secondary/50"
                    )}
                >
                    <span className="flex items-center gap-2">
                        <span className="text-xs font-medium text-muted-foreground">
                            {isImage ? "Generated Image" : "Interactive Chart"}
                        </span>
                    </span>

                    <span className="flex items-center gap-1">
                        <button
                            onClick={() => setIsFullscreen(true)}
                            className={cn(
                                "flex items-center gap-1.5",
                                "px-2 py-1",
                                "text-xs",
                                "rounded",
                                "transition-colors",
                                "text-muted-foreground hover:text-foreground hover:bg-muted"
                            )}
                            title="Fullscreen"
                        >
                            <Maximize2 className="w-3.5 h-3.5" />
                        </button>
                        <button
                            onClick={handleDownload}
                            className={cn(
                                "flex items-center gap-1.5",
                                "px-2 py-1",
                                "text-xs",
                                "rounded",
                                "transition-colors",
                                "text-muted-foreground hover:text-foreground hover:bg-muted"
                            )}
                            title="Download"
                        >
                            <Download className="w-3.5 h-3.5" />
                        </button>
                    </span>
                </span>

                {/* Media content */}
                <span className="block p-4">{renderContent()}</span>
            </span>

            {/* Fullscreen modal */}
            {isFullscreen && (
                <div
                    className="fixed inset-0 z-50 bg-background/95 backdrop-blur-sm animate-in fade-in"
                    onClick={() => setIsFullscreen(false)}
                >
                    <div className="container h-full max-w-7xl mx-auto p-6 flex flex-col">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-lg font-semibold">
                                {isImage ? "Generated Image" : "Interactive Chart"}
                            </h3>
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        handleDownload();
                                    }}
                                    className={cn(
                                        "flex items-center gap-2",
                                        "px-3 py-2",
                                        "text-sm font-medium",
                                        "rounded-lg",
                                        "transition-colors",
                                        "text-muted-foreground hover:text-foreground hover:bg-secondary"
                                    )}
                                >
                                    <Download className="w-4 h-4" />
                                    Download
                                </button>
                                <button
                                    onClick={() => setIsFullscreen(false)}
                                    className={cn(
                                        "flex items-center gap-2",
                                        "px-3 py-2",
                                        "text-sm font-medium",
                                        "rounded-lg",
                                        "transition-colors",
                                        "text-muted-foreground hover:text-foreground hover:bg-secondary"
                                    )}
                                >
                                    <X className="w-4 h-4" />
                                    Close
                                </button>
                            </div>
                        </div>
                        <div
                            className="flex-1 overflow-auto bg-card rounded-lg border border-border p-6"
                            onClick={(e) => e.stopPropagation()}
                        >
                            {renderContent()}
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
