"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { FileText, Download, ExternalLink, Maximize2, Minimize2, FileCode, FileImage, FileJson, FileSpreadsheet, Presentation, ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark, oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { useTheme } from "@/lib/hooks/use-theme";
import { usePreviewStore } from "@/lib/stores/preview-store";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MenuToggle } from "@/components/ui/menu-toggle";
import { getLanguageFromFilename } from "@/lib/utils/file-types";
import type { SlideOutput, SlideOutline } from "@/components/chat/slide-output-panel";

export function FilePreviewSidebar() {
    const { previewFile: file, slideOutput, isOpen, closePreview } = usePreviewStore();
    const [isExpanded, setIsExpanded] = useState(false);
    const t = useTranslations("preview");

    // Render slide preview if slideOutput is set
    if (slideOutput && isOpen) {
        return (
            <SlidePreviewSidebar
                slideOutput={slideOutput}
                isOpen={isOpen}
                isExpanded={isExpanded}
                setIsExpanded={setIsExpanded}
                closePreview={closePreview}
            />
        );
    }

    if (!file || !isOpen) return null;

    const isImage = file.contentType.startsWith("image/");
    const isPDF = file.contentType === "application/pdf";
    const isText = file.contentType.startsWith("text/") ||
        file.contentType === "application/json";
    const isMarkdown = file.filename.endsWith('.md') || file.contentType === "text/markdown";
    const isCode = getLanguageFromFilename(file.filename) !== null && !isMarkdown;

    const handleDownload = () => {
        if (file.previewUrl) {
            const link = document.createElement('a');
            link.href = file.previewUrl;
            link.download = file.filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
    };

    const getFileIcon = () => {
        // File type color coding: Blue (images), Amber (code), Rose (data), Cyan (docs)
        if (isImage) return <FileImage className="w-5 h-5 text-accent-blue" />;
        if (isCode) return <FileCode className="w-5 h-5 text-accent-amber" />;
        if (file.contentType === "application/json") return <FileJson className="w-5 h-5 text-accent-rose" />;
        if (file.contentType?.includes("csv")) return <FileSpreadsheet className="w-5 h-5 text-accent-rose" />;
        if (isMarkdown) return <FileText className="w-5 h-5 text-accent-cyan" />;
        if (file.contentType?.includes("pdf")) return <FileText className="w-5 h-5 text-accent-rose" />;
        return <FileText className="w-5 h-5 text-muted-foreground" />;
    };

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
                className={cn(
                    "fixed right-0 top-0 bottom-0 z-50 flex flex-col transition-colors duration-150",
                    "bg-background/95 border-l border-border",
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
                            {getFileIcon()}
                            <div className="flex flex-col min-w-0">
                                <h3 className="text-sm font-semibold truncate leading-none">
                                    {file.filename}
                                </h3>
                                <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-medium mt-1">
                                    {formatFileSize(file.fileSize)} • {file.contentType.split('/')[1] || file.contentType}
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

                {/* Action Bar */}
                <div className="px-4 py-2 border-b border-border/30 bg-muted/30 flex items-center justify-between shrink-0">
                    <div className="flex items-center gap-2">
                        <Button variant="outline" size="sm" onClick={handleDownload} className="h-8 gap-2">
                            <Download className="w-3.5 h-3.5" />
                            {t("download")}
                        </Button>
                        {file.previewUrl && (
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => window.open(file.previewUrl, '_blank')}
                                className="h-8 gap-2"
                            >
                                <ExternalLink className="w-3.5 h-3.5" />
                                {t("raw")}
                            </Button>
                        )}
                    </div>
                </div>

                {/* Content Area */}
                <ScrollArea className="flex-1">
                    <div className="p-6">
                        {isImage && file.previewUrl ? (
                            <div className="flex items-center justify-center min-h-[200px] bg-secondary/20 rounded-xl border border-border/50 overflow-hidden">
                                <ImagePreview url={file.previewUrl} filename={file.filename} />
                            </div>
                        ) : isPDF && file.previewUrl ? (
                            <PDFPreview url={file.previewUrl} filename={file.filename} />
                        ) : isMarkdown && file.previewUrl ? (
                            <MarkdownPreview url={file.previewUrl} />
                        ) : isCode && file.previewUrl ? (
                            <CodeFilePreview
                                url={file.previewUrl}
                                language={getLanguageFromFilename(file.filename)!}
                                filename={file.filename}
                            />
                        ) : isText && file.previewUrl ? (
                            <div className="font-mono text-sm whitespace-pre-wrap break-words bg-muted/40 p-6 rounded-xl border border-border/50">
                                <TextFilePreview url={file.previewUrl} />
                            </div>
                        ) : (
                            <div className="flex flex-col items-center justify-center py-20 text-center">
                                <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-4">
                                    <FileText className="w-8 h-8 text-muted-foreground/50" />
                                </div>
                                <h4 className="text-base font-medium">{t("noPreview")}</h4>
                                <p className="text-sm text-muted-foreground mt-1 max-w-[240px]">
                                    {t("unsupportedType")}
                                </p>
                                <Button variant="outline" className="mt-6" onClick={handleDownload}>
                                    {t("downloadFile", { filename: file.filename })}
                                </Button>
                            </div>
                        )}
                    </div>
                </ScrollArea>
            </div>
        </>
    );
}

// ---------------------------------------------------------------------------
// Slide Preview Sidebar — single-slide view with prev/next navigation
// ---------------------------------------------------------------------------

interface SlidePreviewSidebarProps {
    slideOutput: SlideOutput;
    isOpen: boolean;
    isExpanded: boolean;
    setIsExpanded: (v: boolean) => void;
    closePreview: () => void;
}

function SlidePreviewSidebar({
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
                                <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-medium mt-1">
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

// ---------------------------------------------------------------------------
// Slide Card — focused single-slide view
// ---------------------------------------------------------------------------

const LAYOUT_COLORS: Record<string, string> = {
    title_slide: "bg-primary/15 text-primary",
    section_header: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
    content: "bg-blue-500/15 text-blue-600 dark:text-blue-400",
    two_column: "bg-cyan-500/15 text-cyan-600 dark:text-cyan-400",
    blank: "bg-muted text-muted-foreground",
};

function SlideCard({ slide, isExpanded = false }: { slide: SlideOutline; isExpanded?: boolean }) {
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
                                "text-[11px] leading-none font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded",
                                colorClass
                            )}>
                                {slide.layout.replaceAll("_", " ")}
                            </span>
                        </div>

                        {/* Title — snug line-height, clamped to 2 lines */}
                        {slide.title && (
                            <h4 className={cn(
                                "font-bold leading-snug mb-1.5 line-clamp-2",
                                isTitleLayout ? "text-lg sm:text-xl" : "text-base"
                            )}>
                                {slide.title}
                            </h4>
                        )}

                        {/* Subtitle — min text-sm for contrast readability */}
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

                        {/* Bullet points — text-sm floor, capped to 3 when images present */}
                        {textElements.length > 0 && (
                            <ul className="space-y-1.5 text-sm leading-relaxed text-foreground/85 mt-1">
                                {(imageElements.length > 0 ? textElements.slice(0, 3) : textElements).map((el, elIdx) => (
                                    <li key={elIdx} className="flex items-start gap-2">
                                        <span className="text-primary/70 mt-[3px] shrink-0 leading-none text-[10px]">&#x25CF;</span>
                                        <span>{el.content}</span>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </div>
                </div>
            </div>

            {/* Speaker notes — collapsible, below the slide */}
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

// ---------------------------------------------------------------------------
// Slide Thumbnail — tiny representation for the filmstrip
// ---------------------------------------------------------------------------

function SlideThumb({ slide, index }: { slide: SlideOutline; index: number }) {
    const isTitleLayout = slide.layout === "title_slide" || slide.layout === "section_header";
    const hasImage = slide.elements.some((el) => el.type === "image" && el.content);
    const textElements = slide.elements.filter((el) => el.type !== "image");

    return (
        <div className={cn(
            "w-full h-full flex flex-col bg-card overflow-hidden relative",
            "p-1.5",
            isTitleLayout ? "items-center justify-center text-center" : "justify-start"
        )}>
            {/* Slide number indicator */}
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

// ---------------------------------------------------------------------------
// File preview sub-components (unchanged)
// ---------------------------------------------------------------------------

function TextFilePreview({ url }: { url: string }) {
    const t = useTranslations("preview");
    const [content, setContent] = useState<string | null>(null);
    const [error, setError] = useState(false);

    useEffect(() => {
        fetch(url, { credentials: 'include' })
            .then(res => res.text())
            .then(text => setContent(text.slice(0, 50000)))
            .catch(() => setError(true));
    }, [url]);

    if (error) return <>{t("failedToLoad")}</>;
    if (content === null) return <>{t("loadingContent")}</>;
    return <>{content}</>;
}

function CodeFilePreview({ url, language, filename }: { url: string; language: string; filename: string }) {
    const t = useTranslations("preview");
    const [content, setContent] = useState<string | null>(null);
    const { resolvedTheme } = useTheme();

    useEffect(() => {
        fetch(url, { credentials: 'include' })
            .then(res => res.text())
            .then(text => setContent(text.slice(0, 50000)))
            .catch(() => setContent("// " + t("failedToLoad")));
    }, [url, t]);

    const isDark = resolvedTheme === "dark";

    if (content === null) {
        return <div className="p-6 text-sm text-muted-foreground">{t("loading")}</div>;
    }

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between px-1">
                <span className="text-xs font-mono text-muted-foreground">{filename}</span>
                <span className="text-[10px] uppercase tracking-wider font-bold text-primary/70 bg-primary/10 px-2 py-0.5 rounded">
                    {language}
                </span>
            </div>
            <div className="rounded-xl border border-border/50 overflow-hidden">
                <SyntaxHighlighter
                    language={language}
                    style={isDark ? oneDark : oneLight}
                    customStyle={{
                        margin: 0,
                        padding: '1.5rem',
                        background: 'transparent',
                        fontSize: '13px',
                        lineHeight: '1.6',
                    }}
                    showLineNumbers
                    lineNumberStyle={{ minWidth: '3em', paddingRight: '1em', opacity: 0.5, textAlign: 'right' }}
                >
                    {content}
                </SyntaxHighlighter>
            </div>
        </div>
    );
}

function MarkdownPreview({ url }: { url: string }) {
    const t = useTranslations("preview");
    const [content, setContent] = useState<string | null>(null);

    useEffect(() => {
        fetch(url, { credentials: 'include' })
            .then(res => res.text())
            .then(text => setContent(text.slice(0, 100000)))
            .catch(() => setContent("# " + t("failedToLoad")));
    }, [url, t]);

    if (content === null) {
        return <div className="p-6 text-sm text-muted-foreground">{t("loading")}</div>;
    }

    return (
        <div className={cn(
            "prose prose-neutral dark:prose-invert max-w-none px-1",
            "prose-headings:font-bold prose-headings:tracking-tight",
            "prose-a:text-primary prose-a:font-medium hover:prose-a:underline",
            "prose-code:text-xs prose-code:bg-muted prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded-md prose-code:before:content-none prose-code:after:content-none",
            "prose-pre:bg-muted/50 prose-pre:border prose-pre:border-border/50 prose-pre:rounded-xl",
            "prose-img:rounded-xl prose-img:border border-border/50",
            "prose-blockquote:border-l-4 prose-blockquote:border-primary/20 prose-blockquote:bg-primary/5 prose-blockquote:py-1 prose-blockquote:px-5 prose-blockquote:rounded-r-lg"
        )}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {content}
            </ReactMarkdown>
        </div>
    );
}

function ImagePreview({ url, filename }: { url: string; filename: string }) {
    const t = useTranslations("preview");
    const [blobUrl, setBlobUrl] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let objectUrl: string | null = null;

        fetch(url, { credentials: 'include' })
            .then(res => {
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                return res.blob();
            })
            .then(blob => {
                objectUrl = URL.createObjectURL(blob);
                setBlobUrl(objectUrl);
            })
            .catch(err => {
                setError(err.message);
            });

        return () => {
            if (objectUrl) URL.revokeObjectURL(objectUrl);
        };
    }, [url]);

    if (error) return <p className="text-destructive p-4">{t("failedToLoadImage", { error })}</p>;
    if (!blobUrl) return <p className="text-muted-foreground animate-pulse p-4">{t("loadingImage")}</p>;

    return (
        <img
            src={blobUrl}
            alt={filename}
            className="max-w-full h-auto object-contain"
        />
    );
}

function PDFPreview({ url, filename }: { url: string; filename: string }) {
    const t = useTranslations("preview");
    const [blobUrl, setBlobUrl] = useState<string | null>(null);

    useEffect(() => {
        let objectUrl: string | null = null;

        fetch(url, { credentials: 'include' })
            .then(res => res.blob())
            .then(blob => {
                objectUrl = URL.createObjectURL(blob);
                setBlobUrl(objectUrl);
            })
            .catch(console.error);

        return () => {
            if (objectUrl) URL.revokeObjectURL(objectUrl);
        };
    }, [url]);

    if (!blobUrl) return <div className="h-[400px] flex items-center justify-center text-muted-foreground">{t("loadingPdf")}</div>;

    return (
        <div className="rounded-xl border border-border/50 overflow-hidden h-[70vh] shadow-inner">
            <iframe
                src={`${blobUrl}#view=FitH&toolbar=0`}
                className="w-full h-full border-0"
                title={filename}
            />
        </div>
    );
}

function formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 10) / 10 + ' ' + sizes[i];
}
