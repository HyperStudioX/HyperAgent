"use client";

import React from "react";
import { SkipBack, SkipForward } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

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

    const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const value = parseInt(e.target.value, 10);
        onStepChange(value);
    };

    return (
        <div className={cn(
            "flex items-center gap-2 px-4 h-12 border-t border-border/50 shrink-0",
            "bg-background",
            className
        )}>
            {/* Previous step */}
            <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={onPrevStep}
                disabled={currentStep <= 0}
                title="Previous step"
            >
                <SkipBack className="w-3.5 h-3.5" />
            </Button>

            {/* Next step */}
            <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={onNextStep}
                disabled={currentStep >= totalSteps}
                title="Next step"
            >
                <SkipForward className="w-3.5 h-3.5" />
            </Button>

            {/* Timeline slider */}
            <div className="flex-1 px-2">
                <input
                    type="range"
                    min={0}
                    max={totalSteps}
                    value={currentStep}
                    onChange={handleSliderChange}
                    className={cn(
                        "w-full h-1 rounded-full appearance-none cursor-pointer",
                        "bg-border",
                        "[&::-webkit-slider-thumb]:appearance-none",
                        "[&::-webkit-slider-thumb]:w-3",
                        "[&::-webkit-slider-thumb]:h-3",
                        "[&::-webkit-slider-thumb]:rounded-full",
                        "[&::-webkit-slider-thumb]:bg-foreground",
                        "[&::-webkit-slider-thumb]:cursor-pointer",
                        "[&::-webkit-slider-thumb]:transition-transform",
                        "[&::-webkit-slider-thumb]:hover:scale-110",
                        "[&::-moz-range-thumb]:w-3",
                        "[&::-moz-range-thumb]:h-3",
                        "[&::-moz-range-thumb]:rounded-full",
                        "[&::-moz-range-thumb]:bg-foreground",
                        "[&::-moz-range-thumb]:border-0",
                        "[&::-moz-range-thumb]:cursor-pointer"
                    )}
                    disabled={totalSteps === 0}
                />
            </div>

            {/* Live indicator or step counter */}
            {isLive ? (
                <button
                    onClick={onGoLive}
                    className={cn(
                        "flex items-center gap-1.5 px-2 py-1 rounded-full",
                        "text-xs font-medium",
                        "bg-blue-500/10 text-blue-500"
                    )}
                >
                    <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
                    {t("live")}
                </button>
            ) : (
                <button
                    onClick={onGoLive}
                    className={cn(
                        "flex items-center gap-1 px-2 py-1 rounded",
                        "text-xs text-muted-foreground hover:text-foreground",
                        "hover:bg-secondary transition-colors"
                    )}
                    title="Go to live"
                >
                    <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/50" />
                    {t("stepOf", { current: currentStep, total: totalSteps })}
                </button>
            )}
        </div>
    );
}
