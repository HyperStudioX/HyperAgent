"use client";

import React, { useState } from "react";
import { FileText, Download, ExternalLink, Maximize2, Minimize2, FileCode, FileImage, FileJson, FileSpreadsheet } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { usePreviewStore } from "@/lib/stores/preview-store";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MenuToggle } from "@/components/ui/menu-toggle";
import { getLanguageFromFilename } from "@/lib/utils/file-types";
import { SlidePreviewSidebar } from "@/components/artifacts/slide-preview";
import { TextFilePreview, CodeFilePreview, MarkdownPreview, ImagePreview, PDFPreview } from "@/components/artifacts/file-previews";

function formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 10) / 10 + ' ' + sizes[i];
}

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
                                <span className="text-xs text-muted-foreground uppercase tracking-wider font-medium mt-1">
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
