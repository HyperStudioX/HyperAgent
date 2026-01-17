"use client";

import React, { useState } from "react";
import { Download, Maximize2, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface VisualizationProps {
    data: string; // Base64 PNG or HTML string
    mimeType: "image/png" | "text/html";
    className?: string;
}

export function Visualization({ data, mimeType, className }: VisualizationProps) {
    const [isFullscreen, setIsFullscreen] = useState(false);
    const [isHovered, setIsHovered] = useState(false);

    const handleDownload = () => {
        if (mimeType === "image/png") {
            const link = document.createElement("a");
            link.href = `data:image/png;base64,${data}`;
            link.download = `visualization-${Date.now()}.png`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        } else if (mimeType === "text/html") {
            const blob = new Blob([data], { type: "text/html" });
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = `visualization-${Date.now()}.html`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
        }
    };

    const renderContent = () => {
        if (mimeType === "image/png") {
            return (
                <img
                    src={`data:image/png;base64,${data}`}
                    alt="Data visualization"
                    className="w-full h-auto rounded-lg"
                />
            );
        } else if (mimeType === "text/html") {
            return (
                <iframe
                    srcDoc={data}
                    title="Interactive visualization"
                    className="w-full h-[500px] rounded-lg border-0"
                    sandbox="allow-scripts allow-same-origin"
                />
            );
        }
        return null;
    };

    return (
        <>
            <div
                className={cn(
                    "relative my-5 rounded-lg overflow-hidden",
                    "ring-1 transition-all duration-300",
                    "bg-secondary/30 ring-border",
                    isHovered && "ring-border/60",
                    className
                )}
                onMouseEnter={() => setIsHovered(true)}
                onMouseLeave={() => setIsHovered(false)}
            >
                {/* Header with controls */}
                <div
                    className={cn(
                        "flex items-center justify-between",
                        "px-3 md:px-4 py-2.5",
                        "border-b border-border",
                        "bg-secondary/50"
                    )}
                >
                    <div className="flex items-center gap-2">
                        <span className="text-xs font-medium text-muted-foreground">
                            {mimeType === "image/png" ? "Chart" : "Interactive Chart"}
                        </span>
                    </div>

                    <div className="flex items-center gap-1">
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
                    </div>
                </div>

                {/* Visualization content */}
                <div className="p-4">{renderContent()}</div>
            </div>

            {/* Fullscreen modal */}
            {isFullscreen && (
                <div
                    className="fixed inset-0 z-50 bg-background/95 backdrop-blur-sm animate-in fade-in"
                    onClick={() => setIsFullscreen(false)}
                >
                    <div className="container h-full max-w-7xl mx-auto p-6 flex flex-col">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-lg font-semibold">
                                {mimeType === "image/png" ? "Chart" : "Interactive Chart"}
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
