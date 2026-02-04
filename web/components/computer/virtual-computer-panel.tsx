"use client";

import React, { useEffect, useCallback, useState } from "react";
import { cn } from "@/lib/utils";
import { useComputerStore, COMPUTER_PANEL_MIN_WIDTH, COMPUTER_PANEL_MAX_WIDTH } from "@/lib/stores/computer-store";
import { useAgentProgressStore } from "@/lib/stores/agent-progress-store";
import { ComputerHeader } from "./computer-header";
import { ComputerStatusBar } from "./computer-status-bar";
import { ComputerTerminalView } from "./computer-terminal-view";
import { ComputerPlanView } from "./computer-plan-view";
import { ComputerBrowserView } from "./computer-browser-view";
import { ComputerFileView } from "./computer-file-view";
import { ComputerPlaybackControls } from "./computer-playback-controls";

export function VirtualComputerPanel() {
    const {
        isOpen,
        panelWidth,
        activeMode,
        terminalLines,
        currentCommand,
        planItems,
        browserStream,
        currentPath,
        files,
        selectedFile,
        isLive,
        currentStep,
        totalSteps,
        closePanel,
        setMode,
        setPanelWidth,
        setBrowserStream,
        setSelectedFile,
        setCurrentPath,
        setCurrentStep,
        setIsLive,
        nextStep,
        prevStep,
    } = useComputerStore();

    const {
        activeProgress,
        setBrowserStream: setAgentBrowserStream,
    } = useAgentProgressStore();

    const [isResizing, setIsResizing] = useState(false);
    const [isDesktop, setIsDesktop] = useState(false);

    // Check if we're on desktop (lg breakpoint = 1024px)
    useEffect(() => {
        const checkDesktop = () => {
            setIsDesktop(window.innerWidth >= 1024);
        };
        checkDesktop();
        window.addEventListener("resize", checkDesktop);
        return () => window.removeEventListener("resize", checkDesktop);
    }, []);

    // Sync browser stream from agent progress store
    useEffect(() => {
        if (activeProgress?.browserStream) {
            setBrowserStream(activeProgress.browserStream);
        }
    }, [activeProgress?.browserStream, setBrowserStream]);

    // Handle close
    const handleClose = useCallback(() => {
        closePanel();
        // Also clear browser stream in agent progress store
        setAgentBrowserStream(null);
    }, [closePanel, setAgentBrowserStream]);

    // Handle browser stream close
    const handleBrowserStreamClose = useCallback(() => {
        setBrowserStream(null);
        setAgentBrowserStream(null);
    }, [setBrowserStream, setAgentBrowserStream]);

    // Resize handlers
    const startResizing = useCallback((e: React.MouseEvent) => {
        e.preventDefault();
        setIsResizing(true);
    }, []);

    const stopResizing = useCallback(() => {
        setIsResizing(false);
    }, []);

    const resize = useCallback(
        (e: MouseEvent) => {
            if (isResizing) {
                // Calculate width from the right edge
                const newWidth = window.innerWidth - e.clientX;
                setPanelWidth(newWidth);
            }
        },
        [isResizing, setPanelWidth]
    );

    // Handle keyboard shortcuts
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape" && isOpen) {
                handleClose();
            }
        };

        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [isOpen, handleClose]);

    // Add/remove event listeners for resize
    useEffect(() => {
        if (isResizing) {
            document.addEventListener("mousemove", resize);
            document.addEventListener("mouseup", stopResizing);
            document.body.style.cursor = "col-resize";
            document.body.style.userSelect = "none";
        }

        return () => {
            document.removeEventListener("mousemove", resize);
            document.removeEventListener("mouseup", stopResizing);
            document.body.style.cursor = "";
            document.body.style.userSelect = "";
        };
    }, [isResizing, resize, stopResizing]);

    // Go to live mode
    const handleGoLive = useCallback(() => {
        setIsLive(true);
    }, [setIsLive]);

    // Determine if agent is actively using the computer
    const isActive = activeProgress?.isStreaming && (
        activeMode === "browser" ? !!browserStream :
        activeMode === "terminal" ? !!currentCommand :
        false
    );

    if (!isOpen) return null;

    return (
        <>
            {/* Mobile backdrop */}
            <div
                className={cn(
                    "fixed inset-0 bg-black/20 z-40 lg:hidden transition-opacity",
                    isOpen ? "opacity-100" : "opacity-0 pointer-events-none"
                )}
                onClick={handleClose}
            />

            {/* Panel */}
            <div
                className={cn(
                    "fixed right-0 top-0 bottom-0 z-50 flex flex-col",
                    "bg-background border-l border-border",
                    "w-full lg:w-auto",
                    !isResizing && "transition-transform duration-300",
                    isOpen ? "translate-x-0" : "translate-x-full"
                )}
                style={{
                    width: isDesktop ? panelWidth : "100%",
                }}
            >
                {/* Resize handle (left edge) */}
                <div
                    className={cn(
                        "absolute top-0 left-0 w-1 h-full cursor-col-resize z-10",
                        "hover:bg-primary/50 active:bg-primary/70",
                        "transition-colors duration-150 hidden lg:block",
                        isResizing && "bg-primary/70"
                    )}
                    onMouseDown={startResizing}
                    role="separator"
                    aria-orientation="vertical"
                    aria-valuenow={panelWidth}
                    aria-valuemin={COMPUTER_PANEL_MIN_WIDTH}
                    aria-valuemax={COMPUTER_PANEL_MAX_WIDTH}
                />

                {/* Header */}
                <ComputerHeader
                    activeMode={activeMode}
                    onModeChange={setMode}
                    onClose={handleClose}
                />

                {/* Status bar */}
                <ComputerStatusBar
                    activeMode={activeMode}
                    currentCommand={currentCommand}
                    isActive={isActive}
                />

                {/* View area */}
                <div className="flex-1 overflow-hidden flex flex-col">
                    {activeMode === "terminal" && (
                        <ComputerTerminalView
                            lines={terminalLines}
                            currentStep={currentStep}
                            isLive={isLive}
                            className="flex-1"
                        />
                    )}

                    {activeMode === "plan" && (
                        <ComputerPlanView
                            items={planItems}
                            className="flex-1"
                        />
                    )}

                    {activeMode === "browser" && (
                        <ComputerBrowserView
                            stream={browserStream}
                            onStreamClose={handleBrowserStreamClose}
                            className="flex-1"
                        />
                    )}

                    {activeMode === "file" && (
                        <ComputerFileView
                            currentPath={currentPath}
                            files={files}
                            selectedFile={selectedFile}
                            onFileSelect={setSelectedFile}
                            onPathChange={setCurrentPath}
                            className="flex-1"
                        />
                    )}
                </div>

                {/* Playback controls */}
                <ComputerPlaybackControls
                    currentStep={currentStep}
                    totalSteps={totalSteps}
                    isLive={isLive}
                    onPrevStep={prevStep}
                    onNextStep={nextStep}
                    onStepChange={setCurrentStep}
                    onGoLive={handleGoLive}
                />
            </div>
        </>
    );
}
