"use client";

import React from "react";
import { X } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { useAgentProgressStore } from "@/lib/stores/agent-progress-store";
import { ComputerViewer } from "@/components/ui/computer-viewer";

/**
 * Browser stream panel - right side panel showing live browser view
 * Only appears when there's an active browser stream
 */
export function BrowserStreamPanel() {
    const tProgress = useTranslations("sidebar.progress");
    const {
        activeProgress,
        isPanelOpen,
        closePanel,
        clearProgress,
        setBrowserStream,
    } = useAgentProgressStore();

    // Only show panel when there's a browser stream
    const hasBrowserStream = activeProgress?.browserStream;
    if (!hasBrowserStream || !isPanelOpen) return null;

    const handleClose = () => {
        closePanel();
        setBrowserStream(null);
        // Clear progress after a short delay
        setTimeout(() => clearProgress(), 300);
    };

    return (
        <>
            {/* Mobile backdrop */}
            <div
                className={cn(
                    "fixed inset-0 bg-black/20 z-40 lg:hidden transition-opacity",
                    isPanelOpen ? "opacity-100" : "opacity-0 pointer-events-none"
                )}
                onClick={handleClose}
            />

            {/* Panel */}
            <div
                className={cn(
                    "fixed right-0 top-0 bottom-0 z-50 flex flex-col transition-transform duration-300",
                    "bg-background border-l border-border",
                    isPanelOpen ? "translate-x-0" : "translate-x-full",
                    "w-full lg:w-[680px]"
                )}
            >
                {/* Header */}
                <div className="flex items-center justify-between px-4 py-3 border-b border-border/50">
                    <span className="text-sm font-medium text-foreground">
                        {tProgress("browserView")}
                    </span>

                    <button
                        onClick={handleClose}
                        className="p-1.5 -m-1 hover:bg-secondary rounded-lg transition-colors"
                        title={tProgress("close")}
                    >
                        <X className="w-4 h-4 text-muted-foreground" />
                    </button>
                </div>

                {/* Browser stream viewer - takes full space */}
                {activeProgress.browserStream && (
                    <div className="flex-1 overflow-hidden">
                        <ComputerViewer
                            stream={activeProgress.browserStream}
                            onClose={() => setBrowserStream(null)}
                            defaultExpanded={true}
                            collapsible={false}
                        />
                    </div>
                )}
            </div>
        </>
    );
}
