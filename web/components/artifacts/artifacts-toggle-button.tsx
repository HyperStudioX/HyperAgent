"use client";

import React from "react";
import { Image as ImageIcon, Presentation } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { usePreviewStore } from "@/lib/stores/preview-store";

interface ArtifactsToggleButtonProps {
    className?: string;
}

export function ArtifactsToggleButton({ className }: ArtifactsToggleButtonProps) {
    const previewFile = usePreviewStore((state) => state.previewFile);
    const slideOutput = usePreviewStore((state) => state.slideOutput);
    const isOpen = usePreviewStore((state) => state.isOpen);
    const closePreview = usePreviewStore((state) => state.closePreview);
    const openPreview = usePreviewStore((state) => state.openPreview);
    const openSlidePreview = usePreviewStore((state) => state.openSlidePreview);

    if (!previewFile && !slideOutput) return null;

    const isSlide = !!slideOutput;

    const handleToggle = () => {
        if (isOpen) {
            closePreview();
        } else if (slideOutput) {
            openSlidePreview(slideOutput);
        } else if (previewFile) {
            openPreview(previewFile);
        }
    };

    return (
        <Button
            variant="ghost"
            size="icon"
            onClick={handleToggle}
            className={cn(
                "h-9 w-9 relative cursor-pointer",
                isOpen && "bg-secondary",
                className
            )}
            aria-label="Artifacts"
            aria-pressed={isOpen}
        >
            {isSlide ? <Presentation className="w-4 h-4" /> : <ImageIcon className="w-4 h-4" />}
        </Button>
    );
}
