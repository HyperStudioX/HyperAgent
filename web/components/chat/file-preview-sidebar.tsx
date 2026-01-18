"use client";

import React, { useEffect, useState } from "react";
import { FileText, Download, ExternalLink, Maximize2, Minimize2, FileCode, FileImage, FileJson, FileSpreadsheet } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark, oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import { cn } from "@/lib/utils";
import { useTheme } from "@/lib/hooks/use-theme";
import { usePreviewStore } from "@/lib/stores/preview-store";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { MenuToggle } from "@/components/ui/menu-toggle";

// Map file extensions to language identifiers for syntax highlighting
const extensionToLanguage: Record<string, string> = {
    'py': 'python',
    'js': 'javascript',
    'jsx': 'jsx',
    'ts': 'typescript',
    'tsx': 'tsx',
    'json': 'json',
    'html': 'html',
    'css': 'css',
    'md': 'markdown',
    'yml': 'yaml',
    'yaml': 'yaml',
    'xml': 'xml',
    'sql': 'sql',
    'sh': 'bash',
    'bash': 'bash',
    'java': 'java',
    'cpp': 'cpp',
    'c': 'c',
    'go': 'go',
    'rs': 'rust',
    'php': 'php',
    'rb': 'ruby',
    'swift': 'swift',
    'kt': 'kotlin',
};

function getFileExtension(filename: string): string {
    const parts = filename.split('.');
    return parts.length > 1 ? parts[parts.length - 1].toLowerCase() : '';
}

function getLanguageFromFilename(filename: string): string | null {
    const ext = getFileExtension(filename);
    return extensionToLanguage[ext] || null;
}

export function FilePreviewSidebar() {
    const { previewFile: file, isOpen, closePreview } = usePreviewStore();
    const [isExpanded, setIsExpanded] = useState(false);
    const { resolvedTheme } = useTheme();

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
        if (isImage) return <FileImage className="w-5 h-5 text-accent-blue transition-transform group-hover:scale-110" />;
        if (isCode) return <FileCode className="w-5 h-5 text-accent-amber transition-transform group-hover:scale-110" />;
        if (file.contentType === "application/json") return <FileJson className="w-5 h-5 text-accent-rose transition-transform group-hover:scale-110" />;
        if (file.contentType?.includes("csv")) return <FileSpreadsheet className="w-5 h-5 text-accent-rose transition-transform group-hover:scale-110" />;
        if (isMarkdown) return <FileText className="w-5 h-5 text-accent-cyan transition-transform group-hover:scale-110" />;
        if (file.contentType?.includes("pdf")) return <FileText className="w-5 h-5 text-accent-rose transition-transform group-hover:scale-110" />;
        return <FileText className="w-5 h-5 text-muted-foreground transition-transform group-hover:scale-110" />;
    };

    return (
        <>
            {/* Backdrop for mobile */}
            <div
                className={cn(
                    "fixed inset-0 bg-black/20 backdrop-blur-sm z-40 lg:hidden transition-opacity duration-300",
                    isOpen ? "opacity-100" : "opacity-0 pointer-events-none"
                )}
                onClick={closePreview}
            />

            {/* Sidebar Container */}
            <div
                className={cn(
                    "fixed right-0 top-0 bottom-0 z-50 flex flex-col transition-all duration-300 ease-in-out",
                    "bg-background/95 backdrop-blur-md border-l border-border shadow-2xl",
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
                            title={isExpanded ? "Minimize" : "Maximize"}
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
                            Download
                        </Button>
                        {file.previewUrl && (
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => window.open(file.previewUrl, '_blank')}
                                className="h-8 gap-2"
                            >
                                <ExternalLink className="w-3.5 h-3.5" />
                                Raw
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
                                <h4 className="text-base font-medium">No Preview Available</h4>
                                <p className="text-sm text-muted-foreground mt-1 max-w-[240px]">
                                    We can't preview this file type directly. You can download it to view it locally.
                                </p>
                                <Button variant="outline" className="mt-6" onClick={handleDownload}>
                                    Download {file.filename}
                                </Button>
                            </div>
                        )}
                    </div>
                </ScrollArea>
            </div>
        </>
    );
}

function TextFilePreview({ url }: { url: string }) {
    const [content, setContent] = useState<string>("Loading content...");

    useEffect(() => {
        fetch(url, { credentials: 'include' })
            .then(res => res.text())
            .then(text => setContent(text.slice(0, 50000)))
            .catch(() => setContent("Failed to load file content. Please try downloading the file."));
    }, [url]);

    return <>{content}</>;
}

function CodeFilePreview({ url, language, filename }: { url: string; language: string; filename: string }) {
    const [content, setContent] = useState<string>("Loading...");
    const { resolvedTheme } = useTheme();

    useEffect(() => {
        fetch(url, { credentials: 'include' })
            .then(res => res.text())
            .then(text => setContent(text.slice(0, 50000)))
            .catch(() => setContent("// Failed to load file content"));
    }, [url]);

    const isDark = resolvedTheme === "dark";

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between px-1">
                <span className="text-xs font-mono text-muted-foreground">{filename}</span>
                <span className="text-[10px] uppercase tracking-wider font-bold text-primary/70 bg-primary/10 px-2 py-0.5 rounded">
                    {language}
                </span>
            </div>
            <div className="rounded-xl border border-border/50 overflow-hidden shadow-sm">
                <SyntaxHighlighter
                    language={language}
                    style={isDark ? oneDark : oneLight}
                    customStyle={{
                        margin: 0,
                        padding: '1.5rem',
                        background: isDark ? 'rgba(30, 30, 30, 0.5)' : 'rgba(250, 250, 250, 0.5)',
                        fontSize: '13px',
                        lineHeight: '1.6',
                    }}
                    showLineNumbers
                    lineNumberStyle={{ minWidth: '3em', paddingRight: '1em', color: isDark ? '#5c6370' : '#a0a1a7', textAlign: 'right' }}
                >
                    {content}
                </SyntaxHighlighter>
            </div>
        </div>
    );
}

function MarkdownPreview({ url }: { url: string }) {
    const [content, setContent] = useState<string>("Loading...");

    useEffect(() => {
        fetch(url, { credentials: 'include' })
            .then(res => res.text())
            .then(text => setContent(text.slice(0, 100000)))
            .catch(() => setContent("# Failed to load content"));
    }, [url]);

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
    const [blobUrl, setBlobUrl] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        fetch(url, { credentials: 'include' })
            .then(res => {
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                return res.blob();
            })
            .then(blob => {
                const objectUrl = URL.createObjectURL(blob);
                setBlobUrl(objectUrl);
            })
            .catch(err => {
                setError(err.message);
            });

        return () => {
            if (blobUrl) URL.revokeObjectURL(blobUrl);
        };
    }, [url]);

    if (error) return <p className="text-destructive p-4">Error loading image: {error}</p>;
    if (!blobUrl) return <p className="text-muted-foreground animate-pulse p-4">Loading image...</p>;

    return (
        <img
            src={blobUrl}
            alt={filename}
            className="max-w-full h-auto object-contain"
        />
    );
}

function PDFPreview({ url, filename }: { url: string; filename: string }) {
    const [blobUrl, setBlobUrl] = useState<string | null>(null);

    useEffect(() => {
        fetch(url, { credentials: 'include' })
            .then(res => res.blob())
            .then(blob => {
                const objectUrl = URL.createObjectURL(blob);
                setBlobUrl(objectUrl);
            })
            .catch(console.error);

        return () => {
            if (blobUrl) URL.revokeObjectURL(blobUrl);
        };
    }, [url]);

    if (!blobUrl) return <div className="h-[400px] flex items-center justify-center text-muted-foreground">Loading PDF...</div>;

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
