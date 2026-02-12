"use client";

import React, { useEffect, useCallback } from "react";
import { SkipBack, SkipForward, Play, Pause } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { useComputerStore, type TimelineEvent, type PlaybackSpeed } from "@/lib/stores/computer-store";

/* Semantic timeline event colors - intentionally using distinct colors per event type for visual differentiation */
const EVENT_TYPE_COLORS: Record<TimelineEvent["type"], string> = {
    terminal: "bg-emerald-500",
    plan: "bg-blue-500",
    browser: "bg-orange-500",
    file: "bg-purple-500",
};

const SPEED_OPTIONS: PlaybackSpeed[] = [1, 2, 4];

// Base interval for 1x playback in ms
const BASE_PLAYBACK_INTERVAL_MS = 800;

interface ComputerPlaybackControlsProps {
    currentStep: number;
    totalSteps: number;
    isLive: boolean;
    onPrevStep: () => void;
    onNextStep: () => void;
    onStepChange: (step: number) => void;
    onGoLive: () => void;
    className?: string;
}

export function ComputerPlaybackControls({
    currentStep,
    totalSteps,
    isLive,
    onPrevStep,
    onNextStep,
    onStepChange,
    onGoLive,
    className,
}: ComputerPlaybackControlsProps) {
    const t = useTranslations("computer");

    const timeline = useComputerStore((state) => state.getTimeline());
    const isPlaying = useComputerStore((state) => state.getIsPlaying());
    const playbackSpeed = useComputerStore((state) => state.getPlaybackSpeed());
    const togglePlayback = useComputerStore((state) => state.togglePlayback);
    const setPlaybackSpeed = useComputerStore((state) => state.setPlaybackSpeed);
    const setMode = useComputerStore((state) => state.setMode);

    // Auto-advance playback timer
    useEffect(() => {
        if (!isPlaying || currentStep >= totalSteps) return;

        // Calculate interval based on speed and optionally time gap between events
        let intervalMs = BASE_PLAYBACK_INTERVAL_MS / playbackSpeed;

        // If we have timeline events with timestamps, use the actual gap (capped)
        if (timeline.length > 0 && currentStep < timeline.length - 1) {
            const currentEvent = timeline[currentStep];
            const nextEvent = timeline[currentStep + 1];
            if (currentEvent && nextEvent) {
                const gap = nextEvent.timestamp - currentEvent.timestamp;
                // Cap the gap at 3 seconds (real time), then apply speed multiplier
                const cappedGap = Math.min(gap, 3000);
                intervalMs = Math.max(200, cappedGap / playbackSpeed);
            }
        }

        const timer = setTimeout(() => {
            onNextStep();
        }, intervalMs);

        return () => clearTimeout(timer);
    }, [isPlaying, currentStep, totalSteps, playbackSpeed, timeline, onNextStep]);

    // Auto-switch view when scrubbing to a different event type
    const handleStepChange = useCallback((step: number) => {
        onStepChange(step);

        // Auto-switch to the relevant view tab
        if (step > 0 && step <= timeline.length) {
            const event = timeline[step - 1];
            if (event) {
                const viewMode = event.type === "browser" ? "browser" as const
                    : event.type === "terminal" ? "terminal" as const
                    : event.type === "file" ? "file" as const
                    : "plan" as const;
                setMode(viewMode);
            }
        }
    }, [onStepChange, timeline, setMode]);

    const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const value = parseInt(e.target.value, 10);
        handleStepChange(value);
    };

    const cycleSpeed = () => {
        const currentIndex = SPEED_OPTIONS.indexOf(playbackSpeed);
        const nextIndex = (currentIndex + 1) % SPEED_OPTIONS.length;
        setPlaybackSpeed(SPEED_OPTIONS[nextIndex]);
    };

    // Compute marker positions for the mini-timeline
    const markers = totalSteps > 0 ? timeline.map((event, index) => ({
        position: ((index + 1) / totalSteps) * 100,
        type: event.type,
    })) : [];

    return (
        <div className={cn(
            "flex items-center gap-1.5 px-3 h-11 border-t border-border/50 shrink-0",
            "bg-background",
            className
        )}>
            {/* Play/Pause */}
            <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={togglePlayback}
                disabled={totalSteps === 0}
                title={isPlaying ? t("pause") : t("play")}
                aria-label={isPlaying ? t("pause") : t("play")}
            >
                {isPlaying ? (
                    <Pause className="w-3.5 h-3.5" />
                ) : (
                    <Play className="w-3.5 h-3.5" />
                )}
            </Button>

            {/* Previous step */}
            <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={onPrevStep}
                disabled={currentStep <= 0}
                title={t("previousStep")}
                aria-label={t("previousStep")}
            >
                <SkipBack className="w-3 h-3" />
            </Button>

            {/* Next step */}
            <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={onNextStep}
                disabled={currentStep >= totalSteps}
                title={t("nextStep")}
                aria-label={t("nextStep")}
            >
                <SkipForward className="w-3 h-3" />
            </Button>

            {/* Timeline with markers */}
            <div className="flex-1 px-1.5 relative">
                {/* Track background with event markers */}
                <div className="relative h-4 flex items-center">
                    {/* Base track */}
                    <div className="absolute inset-x-0 h-1 rounded-full bg-border" />

                    {/* Progress fill */}
                    {totalSteps > 0 && (
                        <div
                            className="absolute left-0 h-1 rounded-full bg-foreground/30"
                            style={{ width: `${(currentStep / totalSteps) * 100}%` }}
                        />
                    )}

                    {/* Event markers */}
                    {markers.map((marker, i) => (
                        <div
                            key={i}
                            className={cn(
                                "absolute w-1.5 h-1.5 rounded-full -translate-x-1/2 z-[1]",
                                EVENT_TYPE_COLORS[marker.type],
                                i + 1 <= currentStep ? "opacity-100" : "opacity-40"
                            )}
                            style={{ left: `${marker.position}%` }}
                        />
                    ))}

                    {/* Hidden range input for interaction */}
                    <input
                        type="range"
                        min={0}
                        max={totalSteps}
                        value={currentStep}
                        onChange={handleSliderChange}
                        aria-label={t("stepOf", { current: currentStep, total: totalSteps })}
                        aria-valuemin={0}
                        aria-valuemax={totalSteps}
                        aria-valuenow={currentStep}
                        className={cn(
                            "absolute inset-0 w-full h-full opacity-0 cursor-pointer z-[2]",
                            "[&::-webkit-slider-thumb]:appearance-none",
                            "[&::-webkit-slider-thumb]:w-3",
                            "[&::-webkit-slider-thumb]:h-3",
                            "[&::-moz-range-thumb]:w-3",
                            "[&::-moz-range-thumb]:h-3"
                        )}
                        disabled={totalSteps === 0}
                    />

                    {/* Playhead indicator */}
                    {totalSteps > 0 && (
                        <div
                            className="absolute w-2.5 h-2.5 rounded-full bg-foreground border-2 border-background -translate-x-1/2 z-[3] pointer-events-none"
                            style={{ left: `${(currentStep / totalSteps) * 100}%` }}
                        />
                    )}
                </div>
            </div>

            {/* Speed control */}
            {!isLive && (
                <button
                    onClick={cycleSpeed}
                    className={cn(
                        "px-1.5 py-0.5 rounded text-[10px] font-mono font-bold",
                        "text-muted-foreground hover:text-foreground",
                        "hover:bg-secondary transition-colors",
                        "min-w-[28px] text-center"
                    )}
                    title={t("playbackSpeed")}
                    aria-label={t("playbackSpeed")}
                >
                    {playbackSpeed}x
                </button>
            )}

            {/* Live indicator or step counter */}
            {isLive ? (
                <button
                    onClick={onGoLive}
                    className={cn(
                        "flex items-center gap-1 px-1.5 py-0.5 rounded-full",
                        "text-[10px] font-medium",
                        "bg-blue-500/10 text-blue-500"
                    )}
                    aria-label={t("live")}
                >
                    <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
                    {t("live")}
                </button>
            ) : (
                <button
                    onClick={onGoLive}
                    className={cn(
                        "flex items-center gap-1 px-1.5 py-0.5 rounded",
                        "text-[10px] text-muted-foreground hover:text-foreground",
                        "hover:bg-secondary transition-colors"
                    )}
                    title={t("goToLive")}
                    aria-label={t("goToLive")}
                >
                    <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/50" />
                    {t("stepOf", { current: currentStep, total: totalSteps })}
                </button>
            )}
        </div>
    );
}
