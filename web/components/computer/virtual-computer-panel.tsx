"use client";

import React, { useEffect, useCallback, useState, useMemo, useRef } from "react";
import { cn } from "@/lib/utils";
import { useComputerStore, COMPUTER_PANEL_MIN_WIDTH, COMPUTER_PANEL_MAX_WIDTH } from "@/lib/stores/computer-store";
import type { ComputerMode, TimelineEventType, TimelineEvent } from "@/lib/stores/computer-store";
import { useAgentProgressStore } from "@/lib/stores/agent-progress-store";
import { ComputerHeader } from "./computer-header";
import { ComputerStatusBar } from "./computer-status-bar";
import { ComputerTerminalView } from "./computer-terminal-view";
import { ComputerPlanView } from "./computer-plan-view";
import { ComputerBrowserView } from "./computer-browser-view";
import { ComputerFileView } from "./computer-file-view";
import { ComputerPlaybackControls } from "./computer-playback-controls";
import { ComputerErrorBoundary } from "./computer-error-boundary";
import { GripHorizontal } from "lucide-react";
import { useTranslations } from "next-intl";

// Module-level empty array constant for referential stability
const EMPTY_ARRAY: never[] = [];
const EMPTY_TIMELINE: TimelineEvent[] = [];

export function VirtualComputerPanel() {
    const t = useTranslations("computer");
    const getModeAriaLabel = useCallback((mode: ComputerMode) => {
        switch (mode) {
            case "terminal":
                return t("terminal");
            case "plan":
                return t("plan");
            case "browser":
                return t("browser");
            case "file":
                return t("files");
            default:
                return mode;
        }
    }, [t]);

    // Global UI state
    const isOpen = useComputerStore((state) => state.isOpen);
    const panelWidth = useComputerStore((state) => state.panelWidth);
    const activeMode = useComputerStore((state) => state.activeMode);
    const followAgent = useComputerStore((state) => state.followAgent);
    const autoOpen = useComputerStore((state) => state.autoOpen);

    // Per-conversation state via direct state access (stable references)
    const terminalLines = useComputerStore((state) => {
        const id = state.activeConversationId;
        return id ? state.conversationStates[id]?.terminalLines ?? EMPTY_ARRAY : EMPTY_ARRAY;
    });
    const currentCommand = useComputerStore((state) => {
        const id = state.activeConversationId;
        return id ? state.conversationStates[id]?.currentCommand ?? null : null;
    });
    const currentCwd = useComputerStore((state) => {
        const id = state.activeConversationId;
        return id ? state.conversationStates[id]?.currentCwd ?? "/home/ubuntu" : "/home/ubuntu";
    });
    const planItems = useComputerStore((state) => {
        const id = state.activeConversationId;
        return id ? state.conversationStates[id]?.planItems ?? EMPTY_ARRAY : EMPTY_ARRAY;
    });
    const browserStream = useComputerStore((state) => {
        const id = state.activeConversationId;
        return id ? state.conversationStates[id]?.browserStream ?? null : null;
    });
    const isLive = useComputerStore((state) => {
        const id = state.activeConversationId;
        return id ? state.conversationStates[id]?.isLive ?? true : true;
    });
    const currentStep = useComputerStore((state) => {
        const id = state.activeConversationId;
        return id ? state.conversationStates[id]?.currentStep ?? 0 : 0;
    });
    const totalSteps = useComputerStore((state) => {
        const id = state.activeConversationId;
        return id ? state.conversationStates[id]?.totalSteps ?? 0 : 0;
    });
    const timeline = useComputerStore((state) => {
        const id = state.activeConversationId;
        return id ? state.conversationStates[id]?.timeline ?? EMPTY_TIMELINE : EMPTY_TIMELINE;
    });

    // Compute visible data slices based on timeline position
    // When not live, only show items that existed at the given timeline step
    const visibleCounts = useMemo(() => {
        if (isLive) {
            return {
                terminal: terminalLines.length,
                plan: planItems.length,
                browser: true,
                file: true,
            };
        }

        // Find the maximum dataIndex for each type within the current timeline window
        const maxIndices: Record<TimelineEventType, number> = {
            terminal: -1,
            plan: -1,
            browser: -1,
            file: -1,
        };

        for (let i = 0; i < Math.min(currentStep, timeline.length); i++) {
            const event = timeline[i];
            if (event.dataIndex > maxIndices[event.type]) {
                maxIndices[event.type] = event.dataIndex;
            }
        }

        return {
            terminal: maxIndices.terminal + 1,
            plan: maxIndices.plan + 1,
            browser: maxIndices.browser >= 0,
            file: maxIndices.file >= 0,
        };
    }, [isLive, currentStep, timeline, terminalLines.length, planItems.length]);

    const visibleTerminalLines = useMemo(
        () => isLive ? terminalLines : terminalLines.slice(0, visibleCounts.terminal),
        [isLive, terminalLines, visibleCounts.terminal]
    );

    const visiblePlanItems = useMemo(
        () => isLive ? planItems : planItems.slice(0, visibleCounts.plan),
        [isLive, planItems, visibleCounts.plan]
    );

    // Split view state
    const splitView = useComputerStore((state) => state.splitView);
    const splitSecondaryMode = useComputerStore((state) => state.splitSecondaryMode);

    // Actions (stable references via getState)
    const closePanel = useComputerStore.getState().closePanel;
    const setModeByUser = useComputerStore.getState().setModeByUser;
    const setPanelWidth = useComputerStore.getState().setPanelWidth;
    const setBrowserStream = useComputerStore.getState().setBrowserStream;
    const setCurrentStep = useComputerStore.getState().setCurrentStep;
    const setIsLive = useComputerStore.getState().setIsLive;
    const nextStep = useComputerStore.getState().nextStep;
    const prevStep = useComputerStore.getState().prevStep;
    const clearTerminal = useComputerStore.getState().clearTerminal;
    const setFollowAgent = useComputerStore.getState().setFollowAgent;
    const setAutoOpen = useComputerStore.getState().setAutoOpen;
    const toggleSplitView = useComputerStore.getState().toggleSplitView;
    const setSplitSecondaryMode = useComputerStore.getState().setSplitSecondaryMode;
    const addTerminalLine = useComputerStore.getState().addTerminalLine;

    const activeProgress = useAgentProgressStore((state) => state.activeProgress);
    const setAgentBrowserStream = useAgentProgressStore.getState().setBrowserStream;

    const [isResizing, setIsResizing] = useState(false);
    const [isDesktop, setIsDesktop] = useState(false);

    // Check if we're on desktop (lg breakpoint = 1024px)
    useEffect(() => {
        const mq = window.matchMedia("(min-width: 1024px)");
        setIsDesktop(mq.matches);
        const handler = (e: MediaQueryListEvent) => setIsDesktop(e.matches);
        mq.addEventListener("change", handler);
        return () => mq.removeEventListener("change", handler);
    }, []);

    // Track tab activity: mark tabs that have new content since user last viewed them
    const lastSeenRef = useRef<Record<ComputerMode, number>>({
        terminal: terminalLines.length,
        plan: planItems.length,
        browser: browserStream ? 1 : 0,
        file: 0,
    });

    // Update last-seen counts when user switches to a tab
    useEffect(() => {
        lastSeenRef.current[activeMode] =
            activeMode === "terminal" ? terminalLines.length :
            activeMode === "plan" ? planItems.length :
            activeMode === "browser" ? (browserStream ? 1 : 0) :
            0;
    }, [activeMode, terminalLines.length, planItems.length, browserStream]);

    const tabActivity = useMemo<Partial<Record<ComputerMode, boolean>>>(() => ({
        terminal: terminalLines.length > lastSeenRef.current.terminal,
        plan: planItems.length > lastSeenRef.current.plan,
        browser: (browserStream ? 1 : 0) > lastSeenRef.current.browser,
    }), [terminalLines.length, planItems.length, browserStream]);

    // Derive sandbox connection status from available signals
    const sandboxStatus = useMemo<"connected" | "disconnected" | "connecting">(() => {
        if (activeProgress?.isStreaming) return "connected";
        if (terminalLines.length > 0 || browserStream || planItems.length > 0) return "connected";
        return "disconnected";
    }, [activeProgress?.isStreaming, terminalLines.length, browserStream, planItems.length]);

    // Sync browser stream from agent progress store (compare by value, not reference)
    const agentStreamUrl = activeProgress?.browserStream?.streamUrl ?? null;
    const agentSandboxId = activeProgress?.browserStream?.sandboxId ?? null;
    useEffect(() => {
        if (activeProgress?.browserStream && agentStreamUrl && agentSandboxId) {
            setBrowserStream(activeProgress.browserStream);
        }
    }, [agentStreamUrl, agentSandboxId, activeProgress?.browserStream, setBrowserStream]);

    // Handle close
    const handleClose = useCallback(() => {
        closePanel();
        // Also clear browser stream in agent progress store
        setAgentBrowserStream(null);
    }, [closePanel, setAgentBrowserStream]);

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
                // Don't close the panel if a child is in fullscreen mode
                // (native fullscreen API or CSS-based fullscreen overlays like the browser view)
                if (document.fullscreenElement) return;
                const fullscreenOverlay = document.querySelector('.fixed.inset-0.z-\\[100\\]');
                if (fullscreenOverlay) return;

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

    // Terminal command handler
    const handleSendTerminalCommand = useCallback(async (command: string) => {
        if (!command.trim()) return;

        const cs = useComputerStore.getState();
        const id = cs.activeConversationId;
        if (!id) return;
        const conv = cs.conversationStates[id];
        if (!conv?.workspaceTaskId) return;

        // Add command to terminal immediately
        addTerminalLine({ type: "command", content: command, cwd: conv.currentCwd });

        try {
            const response = await fetch(`/api/v1/sandbox/exec`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    command,
                    task_id: conv.workspaceTaskId,
                    sandbox_type: conv.workspaceSandboxType || "execution",
                }),
            });
            const data = await response.json();

            if (data.stdout) {
                addTerminalLine({ type: "output", content: data.stdout });
            }
            if (data.stderr) {
                addTerminalLine({ type: "error", content: data.stderr });
            }
        } catch (error) {
            addTerminalLine({ type: "error", content: `Error: ${error}` });
        }
    }, [addTerminalLine]);

    // Split-view resize state
    const [splitRatio, setSplitRatio] = useState(0.5);
    const [isSplitResizing, setIsSplitResizing] = useState(false);
    const splitContainerRef = useRef<HTMLDivElement>(null);

    const startSplitResizing = useCallback((e: React.MouseEvent) => {
        e.preventDefault();
        setIsSplitResizing(true);
    }, []);

    useEffect(() => {
        if (!isSplitResizing) return;

        const handleMouseMove = (e: MouseEvent) => {
            if (!splitContainerRef.current) return;
            const rect = splitContainerRef.current.getBoundingClientRect();
            const ratio = (e.clientY - rect.top) / rect.height;
            setSplitRatio(Math.min(Math.max(ratio, 0.2), 0.8));
        };

        const handleMouseUp = () => {
            setIsSplitResizing(false);
        };

        document.addEventListener("mousemove", handleMouseMove);
        document.addEventListener("mouseup", handleMouseUp);
        document.body.style.cursor = "row-resize";
        document.body.style.userSelect = "none";

        return () => {
            document.removeEventListener("mousemove", handleMouseMove);
            document.removeEventListener("mouseup", handleMouseUp);
            document.body.style.cursor = "";
            document.body.style.userSelect = "";
        };
    }, [isSplitResizing]);

    // Helper to render a view for a given mode
    const renderViewForMode = useCallback((mode: ComputerMode) => {
        switch (mode) {
            case "terminal":
                return (
                    <ComputerTerminalView
                        lines={visibleTerminalLines}
                        isLive={isLive}
                        currentCommand={currentCommand}
                        currentCwd={currentCwd}
                        onClear={clearTerminal}
                        onSendCommand={handleSendTerminalCommand}
                        className="flex-1"
                    />
                );
            case "plan":
                return (
                    <ComputerPlanView
                        items={visiblePlanItems}
                        className="flex-1"
                    />
                );
            case "browser":
                return (
                    <ComputerBrowserView
                        stream={browserStream}
                        className="flex-1"
                    />
                );
            case "file":
                return (
                    <ComputerFileView className="flex-1" />
                );
            default:
                return null;
        }
    }, [visibleTerminalLines, isLive, currentCommand, currentCwd, clearTerminal, handleSendTerminalCommand, visiblePlanItems, browserStream]);

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
                    "fixed inset-0 bg-black/40 z-40 lg:hidden transition-opacity",
                    isOpen ? "opacity-100" : "opacity-0 pointer-events-none"
                )}
                onClick={handleClose}
                aria-hidden="true"
            />

            {/* Panel */}
            <div
                className={cn(
                    "fixed right-0 top-0 bottom-0 z-50 flex flex-col",
                    "bg-background border-l border-border",
                    "w-full lg:w-auto",
                    !isDesktop && "pt-safe pb-safe",
                    !isResizing && "transition-transform duration-300",
                    isOpen ? "translate-x-0" : "translate-x-full"
                )}
                style={{
                    width: isDesktop ? panelWidth : "100%",
                }}
                role="complementary"
                aria-label={t("panelTitle")}
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
                    aria-label={t("resizeHandle")}
                    tabIndex={0}
                />

                {/* Header */}
                <ComputerHeader
                    activeMode={activeMode}
                    onModeChange={setModeByUser}
                    onClose={handleClose}
                    sandboxStatus={sandboxStatus}
                    tabActivity={tabActivity}
                    followAgent={followAgent}
                    autoOpen={autoOpen}
                    onFollowAgentChange={setFollowAgent}
                    onAutoOpenChange={setAutoOpen}
                    splitView={splitView}
                    onToggleSplitView={toggleSplitView}
                />

                {/* Status bar */}
                <ComputerStatusBar
                    activeMode={activeMode}
                    currentCommand={currentCommand}
                    isActive={isActive}
                />

                {/* View area with error boundary */}
                <ComputerErrorBoundary
                    translations={{
                        title: t("errorBoundary.title"),
                        maxRetries: t("errorBoundary.maxRetries"),
                        retry: (count: number) => t("errorBoundary.retry", { count }),
                        fallbackErrorMessage: t("errorBoundary.fallbackMessage"),
                    }}
                >
                    {splitView && splitSecondaryMode ? (
                        <div
                            ref={splitContainerRef}
                            className="flex-1 overflow-hidden flex flex-col"
                        >
                            {/* Primary view (top) */}
                            <div
                                className="overflow-hidden flex flex-col"
                                style={{ height: `${splitRatio * 100}%` }}
                                role="tabpanel"
                                aria-label={getModeAriaLabel(activeMode)}
                            >
                                {renderViewForMode(activeMode)}
                            </div>

                            {/* Split resize handle */}
                            <div
                                className={cn(
                                    "h-1.5 flex items-center justify-center cursor-row-resize shrink-0",
                                    "bg-border/30 hover:bg-primary/30 active:bg-primary/50",
                                    "transition-colors duration-150",
                                    isSplitResizing && "bg-primary/50"
                                )}
                                onMouseDown={startSplitResizing}
                                role="separator"
                                aria-orientation="horizontal"
                                aria-label={t("resizeHandle")}
                            >
                                <GripHorizontal className="w-4 h-4 text-muted-foreground/50" />
                            </div>

                            {/* Secondary view (bottom) */}
                            <div
                                className="overflow-hidden flex flex-col"
                                style={{ height: `${(1 - splitRatio) * 100}%` }}
                                role="tabpanel"
                                aria-label={getModeAriaLabel(splitSecondaryMode)}
                            >
                                {/* Secondary mode selector */}
                                <div className="flex items-center gap-1 px-2 h-7 border-b border-border/30 bg-secondary/20 shrink-0">
                                    {(["terminal", "browser", "file", "plan"] as ComputerMode[])
                                        .filter((m) => m !== activeMode)
                                        .map((mode) => (
                                            <button
                                                key={mode}
                                                className={cn(
                                                    "px-2 py-0.5 text-[11px] rounded font-medium transition-colors",
                                                    mode === splitSecondaryMode
                                                        ? "bg-secondary text-foreground"
                                                        : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
                                                )}
                                                onClick={() => setSplitSecondaryMode(mode)}
                                            >
                                                {t(mode === "file" ? "files" : mode)}
                                            </button>
                                        ))
                                    }
                                </div>
                                {renderViewForMode(splitSecondaryMode)}
                            </div>
                        </div>
                    ) : (
                        <div
                            className="flex-1 overflow-hidden flex flex-col"
                            role="tabpanel"
                            aria-label={getModeAriaLabel(activeMode)}
                        >
                            {renderViewForMode(activeMode)}
                        </div>
                    )}
                </ComputerErrorBoundary>

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
