"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { Download, Maximize2, Minimize2, Presentation, ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { MenuToggle } from "@/components/ui/menu-toggle";
import type { SlideOutput, SlideOutline } from "@/components/chat/slide-output-panel";

export const LAYOUT_COLORS: Record<string, string> = {
    title_slide: "bg-accent-cyan/10 text-accent-cyan",
    section_header: "bg-accent-cyan/10 text-accent-cyan",
    content: "bg-accent-cyan/10 text-accent-cyan",
    two_column: "bg-accent-cyan/10 text-accent-cyan",
    blank: "bg-accent-cyan/10 text-accent-cyan",
};

interface SlidePreviewSidebarProps {
    slideOutput: SlideOutput;
    isOpen: boolean;
    isExpanded: boolean;
    setIsExpanded: (v: boolean) => void;
    closePreview: () => void;
}

export function SlidePreviewSidebar({
    slideOutput,
    isOpen,
    isExpanded,
    setIsExpanded,
    closePreview,
}: SlidePreviewSidebarProps) {
    const t = useTranslations("preview");
    const slides = slideOutput.slide_outline || [];
    const [currentIndex, setCurrentIndex] = useState(0);
    const containerRef = useRef<HTMLDivElement>(null);
    const thumbStripRef = useRef<HTMLDivElement>(null);

    const [transitioning, setTransitioning] = useState(false);

    const canPrev = currentIndex > 0;
    const canNext = currentIndex < slides.length - 1;

    const goTo = useCallback((idx: number) => {
        const clamped = Math.max(0, Math.min(idx, slides.length - 1));
        if (clamped === currentIndex) return;
        setTransitioning(true);
        setTimeout(() => {
            setCurrentIndex(clamped);
            setTransitioning(false);
        }, 50);
    }, [slides.length, currentIndex]);

    const goPrev = useCallback(() => { if (canPrev) goTo(currentIndex - 1); }, [canPrev, currentIndex, goTo]);
    const goNext = useCallback(() => { if (canNext) goTo(currentIndex + 1); }, [canNext, currentIndex, goTo]);

    // Keyboard navigation — arrow keys
    useEffect(() => {
        const el = containerRef.current;
        if (!el) return;

        const handler = (e: KeyboardEvent) => {
            if (e.key === "ArrowLeft" || e.key === "ArrowUp") { e.preventDefault(); goPrev(); }
            if (e.key === "ArrowRight" || e.key === "ArrowDown") { e.preventDefault(); goNext(); }
            if (e.key === "Home") { e.preventDefault(); goTo(0); }
            if (e.key === "End") { e.preventDefault(); goTo(slides.length - 1); }
        };
        el.addEventListener("keydown", handler);
        return () => el.removeEventListener("keydown", handler);
    }, [goPrev, goNext, goTo, slides.length]);

    // Auto-scroll active thumbnail into view
    useEffect(() => {
        const strip = thumbStripRef.current;
        if (!strip) return;
        const active = strip.children[currentIndex] as HTMLElement | undefined;
        active?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
    }, [currentIndex]);

    const handleDownload = () => {
        if (slideOutput.download_url) {
            const link = document.createElement("a");
            link.href = slideOutput.download_url;
            link.download = `${slideOutput.title || "presentation"}.pptx`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
    };

    const currentSlide = slides[currentIndex];

    return (
        <>
            {/* Backdrop for mobile */}
            <div
                className={cn(
                    "fixed inset-0 bg-black/40 z-40 lg:hidden transition-opacity duration-300",
                    isOpen ? "opacity-100" : "opacity-0 pointer-events-none"
                )}
                onClick={closePreview}
            />

            {/* Sidebar Container */}
            <div
                ref={containerRef}
                tabIndex={0}
                className={cn(
                    "fixed right-0 top-0 bottom-0 z-50 flex flex-col transition-colors duration-150",
                    "bg-background/95 border-l border-border outline-none",
                    isExpanded ? "w-full" : "w-full lg:w-[450px] xl:w-[600px]",
                    isOpen ? "translate-x-0" : "translate-x-full"
                )}
            >
                {/* Header */}
                <div className="flex items-center justify-between px-4 h-14 border-b border-border/50 shrink-0">
                    <div className="flex items-center gap-3 min-w-0">
                        <MenuToggle
                            isOpen={true}
                            onClick={closePreview}
                            className="lg:hidden"
                        />
                        <div className="flex items-center gap-2.5 truncate">
                            <Presentation className="w-5 h-5 text-primary" />
                            <div className="flex flex-col min-w-0">
                                <h3 className="text-sm font-semibold truncate leading-none">
                                    {slideOutput.title}
                                </h3>
                                <span className="text-xs text-muted-foreground uppercase tracking-wider font-medium mt-1">
                                    {t("slidePreview")}
                                </span>
                            </div>
                        </div>
                    </div>

                    <div className="flex items-center gap-1">
                        <Button
                            variant="ghost"
                            size="icon"
                            className="hidden lg:flex"
                            onClick={() => setIsExpanded(!isExpanded)}
                            title={isExpanded ? t("minimize") : t("maximize")}
                        >
                            {isExpanded ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
                        </Button>
                        <MenuToggle
                            isOpen={true}
                            onClick={closePreview}
                            className="hidden lg:flex"
                        />
                    </div>
                </div>

                {/* Action Bar: download + nav controls */}
                <div className="px-4 py-2 border-b border-border/30 bg-muted/30 flex items-center justify-between shrink-0">
                    <Button variant="outline" size="sm" onClick={handleDownload} className="h-8 gap-2">
                        <Download className="w-3.5 h-3.5" />
                        {t("download")}
                    </Button>

                    {/* Prev / counter / Next */}
                    {slides.length > 0 && (
                        <div className="flex items-center gap-1">
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8"
                                onClick={goPrev}
                                disabled={!canPrev}
                                title={t("previousSlide")}
                            >
                                <ChevronLeft className="w-4 h-4" />
                            </Button>
                            <span className="text-xs tabular-nums text-muted-foreground min-w-[4.5rem] text-center select-none">
                                {t("slideOf", { current: currentIndex + 1, total: slides.length })}
                            </span>
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8"
                                onClick={goNext}
                                disabled={!canNext}
                                title={t("nextSlide")}
                            >
                                <ChevronRight className="w-4 h-4" />
                            </Button>
                        </div>
                    )}
                </div>

                {/* Main slide area */}
                {slides.length > 0 && currentSlide ? (
                    <div className="flex-1 flex flex-col min-h-0">
                        {/* Active slide card */}
                        <div className={cn(
                            "flex-1 min-h-0 p-4 overflow-y-auto transition-opacity duration-150",
                            transitioning ? "opacity-0" : "opacity-100"
                        )}>
                            <SlideCard slide={currentSlide} isExpanded={isExpanded} />
                        </div>

                        {/* Thumbnail strip */}
                        {slides.length > 1 && (
                            <div className="shrink-0 border-t border-border/30 bg-muted/20 px-3 py-2.5">
                                <div
                                    ref={thumbStripRef}
                                    className="flex gap-2 overflow-x-auto scrollbar-none"
                                    role="tablist"
                                    aria-label={t("slideDeck")}
                                >
                                    {slides.map((slide, idx) => (
                                        <button
                                            key={idx}
                                            role="tab"
                                            aria-selected={idx === currentIndex}
                                            aria-label={`${idx + 1}. ${slide.title || slide.layout}`}
                                            title={`${idx + 1}. ${slide.title || slide.layout}`}
                                            onClick={() => goTo(idx)}
                                            className={cn(
                                                "shrink-0 rounded-md border overflow-hidden transition-all duration-150 cursor-pointer",
                                                "focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1 outline-none",
                                                idx === currentIndex
                                                    ? "border-primary ring-1 ring-primary/30 shadow-sm"
                                                    : "border-border/40 hover:border-border opacity-70 hover:opacity-100"
                                            )}
                                            style={{ width: 80, height: 45 }}
                                        >
                                            <SlideThumb slide={slide} index={idx} />
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="flex-1 flex flex-col items-center justify-center py-20 text-center">
                        <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-4">
                            <Presentation className="w-8 h-8 text-muted-foreground/50" />
                        </div>
                        <h4 className="text-base font-medium">{t("noPreview")}</h4>
                    </div>
                )}
            </div>
        </>
    );
}

export function SlideCard({ slide, isExpanded = false }: { slide: SlideOutline; isExpanded?: boolean }) {
    const t = useTranslations("preview");
    const isTitleLayout = slide.layout === "title_slide" || slide.layout === "section_header";
    const colorClass = LAYOUT_COLORS[slide.layout] || LAYOUT_COLORS.content;

    const textElements = slide.elements.filter((el) => el.type !== "image");
    const imageElements = slide.elements.filter((el) => el.type === "image" && el.content);

    return (
        <div className={cn(
            "flex flex-col gap-3",
            isExpanded && "max-w-4xl mx-auto w-full"
        )}>
            {/* Slide surface — fixed 16:9 aspect ratio, capped in expanded mode */}
            <div className="rounded-xl border border-border/50 overflow-hidden bg-card shadow-sm">
                <div className="relative w-full" style={{ paddingBottom: "56.25%" }}>
                    <div className={cn(
                        "absolute inset-0 flex flex-col overflow-auto",
                        "p-5 sm:p-6",
                        isTitleLayout ? "items-center justify-center text-center" : "justify-start"
                    )}>
                        {/* Layout badge */}
                        <div className={cn(
                            "flex items-center gap-2 mb-2",
                            isTitleLayout ? "justify-center" : "justify-start"
                        )}>
                            <span className={cn(
                                "text-xs leading-none font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded",
                                colorClass
                            )}>
                                {slide.layout.replaceAll("_", " ")}
                            </span>
                        </div>

                        {/* Title */}
                        {slide.title && (
                            <h4 className={cn(
                                "font-bold leading-snug mb-1.5 line-clamp-2",
                                isTitleLayout ? "text-lg sm:text-xl" : "text-base"
                            )}>
                                {slide.title}
                            </h4>
                        )}

                        {/* Subtitle */}
                        {slide.subtitle && (
                            <p className={cn(
                                "text-muted-foreground leading-normal mb-2",
                                isTitleLayout ? "text-sm" : "text-sm"
                            )}>
                                {slide.subtitle}
                            </p>
                        )}

                        {/* Generated image */}
                        {imageElements.length > 0 && (
                            <div className="mt-2 flex-1 min-h-0 flex items-center justify-center">
                                <img
                                    src={imageElements[0].content}
                                    alt={slide.title || "Slide image"}
                                    className="max-w-full max-h-full object-contain rounded-lg"
                                />
                            </div>
                        )}

                        {/* Bullet points */}
                        {textElements.length > 0 && (
                            <ul className="space-y-1.5 text-sm leading-relaxed text-foreground/85 mt-1">
                                {(imageElements.length > 0 ? textElements.slice(0, 3) : textElements).map((el, elIdx) => (
                                    <li key={elIdx} className="flex items-start gap-2">
                                        <span className="text-primary/70 mt-[3px] shrink-0 leading-none text-xs">&#x25CF;</span>
                                        <span>{el.content}</span>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </div>
                </div>
            </div>

            {/* Speaker notes — collapsible */}
            {slide.notes && (
                <details className="rounded-lg border border-border/30 bg-muted/20 group">
                    <summary className="flex items-center gap-2 px-4 py-2.5 cursor-pointer text-xs font-medium text-muted-foreground hover:text-foreground transition-colors duration-150 select-none">
                        <ChevronDown className="w-3.5 h-3.5 transition-transform duration-150 group-open:rotate-180" />
                        {t("speakerNotes")}
                    </summary>
                    <div className="px-4 pb-3 text-sm text-muted-foreground leading-relaxed">
                        {slide.notes}
                    </div>
                </details>
            )}
        </div>
    );
}

export function SlideThumb({ slide, index }: { slide: SlideOutline; index: number }) {
    const isTitleLayout = slide.layout === "title_slide" || slide.layout === "section_header";
    const hasImage = slide.elements.some((el) => el.type === "image" && el.content);
    const textElements = slide.elements.filter((el) => el.type !== "image");

    return (
        <div className={cn(
            "w-full h-full flex flex-col bg-card overflow-hidden relative",
            "p-1.5",
            isTitleLayout ? "items-center justify-center text-center" : "justify-start"
        )}>
            <span className="absolute top-0.5 left-1 text-[6px] text-muted-foreground/50 leading-none select-none">
                {index + 1}
            </span>
            <span className={cn(
                "font-semibold leading-tight truncate w-full",
                isTitleLayout ? "text-[8px]" : "text-[7px]"
            )}>
                {slide.title || slide.layout.replaceAll("_", " ")}
            </span>
            {hasImage && !isTitleLayout && (
                <div className="mt-0.5 w-full h-[4px] rounded-sm bg-primary/15" />
            )}
            {textElements.length > 0 && !isTitleLayout && (
                <div className="mt-0.5 space-y-px w-full">
                    {textElements.slice(0, hasImage ? 2 : 3).map((_, i) => (
                        <div key={i} className="h-[2px] bg-muted-foreground/20 rounded-full" style={{ width: `${70 - i * 10}%` }} />
                    ))}
                </div>
            )}
        </div>
    );
}
