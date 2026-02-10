"use client";

import React, { useState, useCallback } from "react";
import {
    FileText,
    Download,
    Loader2,
    AlertCircle,
    FileCode,
    Copy,
    Check,
    FileSearch,
} from "lucide-react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark, oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { useTheme } from "@/lib/hooks/use-theme";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";

// Map file extensions to language identifiers for syntax highlighting
const extensionToLanguage: Record<string, string> = {
    py: "python",
    js: "javascript",
    jsx: "jsx",
    ts: "typescript",
    tsx: "tsx",
    json: "json",
    html: "html",
    css: "css",
    scss: "scss",
    less: "less",
    md: "markdown",
    yml: "yaml",
    yaml: "yaml",
    xml: "xml",
    sql: "sql",
    sh: "bash",
    bash: "bash",
    zsh: "bash",
    java: "java",
    cpp: "cpp",
    c: "c",
    h: "c",
    hpp: "cpp",
    go: "go",
    rs: "rust",
    php: "php",
    rb: "ruby",
    swift: "swift",
    kt: "kotlin",
    scala: "scala",
    r: "r",
    lua: "lua",
    vim: "vim",
    dockerfile: "dockerfile",
    makefile: "makefile",
    toml: "toml",
    ini: "ini",
    env: "bash",
    gitignore: "bash",
};

function getFileExtension(filename: string): string {
    const parts = filename.split(".");
    if (parts.length === 1) {
        // Handle files like Dockerfile, Makefile
        const lowerName = filename.toLowerCase();
        if (lowerName === "dockerfile") return "dockerfile";
        if (lowerName === "makefile") return "makefile";
        return "";
    }
    return parts[parts.length - 1].toLowerCase();
}

function getLanguageFromFilename(filename: string): string | null {
    const ext = getFileExtension(filename);
    return extensionToLanguage[ext] || null;
}

function isImageFile(filename: string): boolean {
    const ext = getFileExtension(filename);
    return ["png", "jpg", "jpeg", "gif", "svg", "webp", "ico", "bmp"].includes(ext);
}

interface ComputerFileContentProps {
    filename: string;
    content: string | null;
    isLoading: boolean;
    error: string | null;
    isBinary: boolean;
    onDownload?: () => void;
    className?: string;
}

function ContentHeader({
    filename,
    language,
    content,
    onDownload,
}: {
    filename: string;
    language: string | null;
    content: string | null;
    onDownload?: () => void;
}) {
    const t = useTranslations("computer");
    const [copied, setCopied] = useState(false);

    const handleCopy = useCallback(async () => {
        if (!content) return;
        try {
            await navigator.clipboard.writeText(content);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch {
            // Fallback for older browsers
            const textarea = document.createElement("textarea");
            textarea.value = content;
            textarea.style.position = "fixed";
            textarea.style.opacity = "0";
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand("copy");
            document.body.removeChild(textarea);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }
    }, [content]);

    const handleDownload = useCallback(() => {
        if (!content || !filename) return;
        if (onDownload) {
            onDownload();
            return;
        }
        // Client-side download from content
        const blob = new Blob([content], { type: "text/plain" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }, [content, filename, onDownload]);

    const icon = language ? (
        <FileCode className="w-3.5 h-3.5 text-accent-amber" />
    ) : (
        <FileText className="w-3.5 h-3.5 text-muted-foreground" />
    );

    return (
        <div className="flex items-center justify-between px-3 py-1.5 border-b border-border/30 bg-secondary/10">
            <div className="flex items-center gap-2 min-w-0">
                {icon}
                <span className="text-xs font-mono text-muted-foreground truncate max-w-[140px]">
                    {filename}
                </span>
                {language && (
                    <span className="text-[10px] uppercase tracking-wider font-bold text-primary/70 bg-primary/10 px-1.5 py-0.5 rounded">
                        {language}
                    </span>
                )}
            </div>
            <div className="flex items-center gap-0.5">
                {content && (
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6"
                        onClick={handleCopy}
                        title={copied ? t("workspace.copied") : t("workspace.copyContent")}
                    >
                        {copied ? (
                            <Check className="w-3.5 h-3.5 text-green-500" />
                        ) : (
                            <Copy className="w-3.5 h-3.5" />
                        )}
                    </Button>
                )}
                {content && (
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6"
                        onClick={handleDownload}
                        title={t("workspace.download")}
                    >
                        <Download className="w-3.5 h-3.5" />
                    </Button>
                )}
            </div>
        </div>
    );
}

export function ComputerFileContent({
    filename,
    content,
    isLoading,
    error,
    isBinary,
    onDownload,
    className,
}: ComputerFileContentProps) {
    const t = useTranslations("computer");
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === "dark";

    const language = getLanguageFromFilename(filename);
    const isImage = isImageFile(filename);

    // Loading state
    if (isLoading) {
        return (
            <div className={cn("flex flex-col items-center justify-center h-full py-12", className)}>
                <Loader2 className="w-8 h-8 text-muted-foreground animate-spin mb-3" />
                <p className="text-sm text-muted-foreground">{t("workspace.loading")}</p>
            </div>
        );
    }

    // Error state
    if (error) {
        return (
            <div className={cn("flex flex-col items-center justify-center h-full py-12", className)}>
                <div className="w-12 h-12 rounded-xl bg-destructive/10 flex items-center justify-center mb-3">
                    <AlertCircle className="w-6 h-6 text-destructive" />
                </div>
                <p className="text-sm text-destructive text-center px-4">{error}</p>
            </div>
        );
    }

    // No content state - improved empty state
    if (content === null) {
        return (
            <div className={cn("flex flex-col items-center justify-center h-full py-12", className)}>
                <div className="w-12 h-12 rounded-xl bg-secondary/50 flex items-center justify-center mb-3">
                    <FileSearch className="w-6 h-6 text-muted-foreground/40" />
                </div>
                <p className="text-sm text-muted-foreground">{t("workspace.selectFile")}</p>
            </div>
        );
    }

    // Binary file - show download option
    if (isBinary && !isImage) {
        return (
            <div className={cn("flex flex-col items-center justify-center h-full py-12", className)}>
                <div className="w-12 h-12 rounded-xl bg-secondary/50 flex items-center justify-center mb-4">
                    <FileText className="w-6 h-6 text-muted-foreground/50" />
                </div>
                <p className="text-sm font-medium mb-2">{filename}</p>
                <p className="text-xs text-muted-foreground mb-4">{t("workspace.noPreview")}</p>
                {onDownload && (
                    <Button variant="outline" size="sm" onClick={onDownload}>
                        <Download className="w-4 h-4 mr-2" />
                        {t("workspace.download")}
                    </Button>
                )}
            </div>
        );
    }

    // Image file - display base64 image (with size guard)
    if (isImage && isBinary) {
        const MAX_IMAGE_SIZE = 5 * 1024 * 1024; // 5MB
        if (content.length > MAX_IMAGE_SIZE) {
            return (
                <div className={cn("flex flex-col items-center justify-center h-full py-12", className)}>
                    <FileText className="w-12 h-12 text-muted-foreground/50 mb-4" />
                    <p className="text-sm font-medium mb-2">{filename}</p>
                    <p className="text-xs text-muted-foreground">
                        File too large to preview ({(content.length / (1024 * 1024)).toFixed(1)} MB)
                    </p>
                </div>
            );
        }

        const ext = getFileExtension(filename);
        const mimeMap: Record<string, string> = {
            svg: "image/svg+xml",
            jpg: "image/jpeg",
            jpeg: "image/jpeg",
            png: "image/png",
            gif: "image/gif",
            webp: "image/webp",
            ico: "image/x-icon",
            bmp: "image/bmp",
        };
        const mimeType = mimeMap[ext] || `image/${ext}`;
        return (
            <div className={cn("flex items-center justify-center h-full p-4", className)}>
                <img
                    src={`data:${mimeType};base64,${content}`}
                    alt={filename}
                    className="max-w-full max-h-full object-contain rounded-lg"
                />
            </div>
        );
    }

    // Code file with syntax highlighting (plain text fallback for large files)
    const SYNTAX_HIGHLIGHT_SIZE_LIMIT = 100 * 1024; // 100KB
    if (language) {
        const usePlainText = content.length > SYNTAX_HIGHLIGHT_SIZE_LIMIT;
        return (
            <div className={cn("flex flex-col h-full", className)}>
                <ContentHeader
                    filename={filename}
                    language={language}
                    content={content}
                    onDownload={onDownload}
                />
                <ScrollArea className="flex-1">
                    <div className="p-0">
                        {usePlainText ? (
                            <PlainTextWithLineNumbers content={content} />
                        ) : (
                            <SyntaxHighlighter
                                language={language}
                                style={isDark ? oneDark : oneLight}
                                customStyle={{
                                    margin: 0,
                                    padding: "0.75rem 1rem",
                                    background: "transparent",
                                    fontSize: "12px",
                                    lineHeight: "1.5",
                                }}
                                showLineNumbers
                                lineNumberStyle={{
                                    minWidth: "2.5em",
                                    paddingRight: "0.75em",
                                    opacity: 0.4,
                                    textAlign: "right",
                                }}
                            >
                                {content}
                            </SyntaxHighlighter>
                        )}
                    </div>
                </ScrollArea>
            </div>
        );
    }

    // Plain text file with line numbers
    return (
        <div className={cn("flex flex-col h-full", className)}>
            <ContentHeader
                filename={filename}
                language={null}
                content={content}
                onDownload={onDownload}
            />
            <ScrollArea className="flex-1">
                <div className="p-0">
                    <PlainTextWithLineNumbers content={content} />
                </div>
            </ScrollArea>
        </div>
    );
}

function PlainTextWithLineNumbers({ content }: { content: string }) {
    const lines = content.split("\n");
    const gutterWidth = String(lines.length).length;

    return (
        <pre className="text-xs font-mono leading-relaxed">
            <table className="border-collapse w-full">
                <tbody>
                    {lines.map((line, i) => (
                        <tr key={i} className="hover:bg-secondary/30">
                            <td
                                className="text-right select-none text-muted-foreground/40 pr-3 pl-3 align-top"
                                style={{ minWidth: `${gutterWidth + 2}ch` }}
                            >
                                {i + 1}
                            </td>
                            <td className="whitespace-pre-wrap break-words text-foreground/90 pr-4">
                                {line || "\n"}
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </pre>
    );
}
