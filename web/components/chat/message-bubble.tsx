"use client";

import React, { useState, memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useTranslations } from "next-intl";
import Image from "next/image";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark, oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import { Copy, Check, Terminal, RotateCcw, FileText, ImageIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTheme } from "@/lib/hooks/use-theme";
import { usePreviewStore } from "@/lib/stores/preview-store";
import { GeneratedMedia } from "@/components/chat/generated-media";
import type { Message, FileAttachment, GeneratedImage, AgentEvent } from "@/lib/types";

// Normalized image structure for consistent handling
interface NormalizedImage {
    index: number;
    data?: string;
    url?: string;
    storageKey?: string;
    fileId?: string;
    mimeType: "image/png" | "image/jpeg" | "image/gif" | "image/webp" | "text/html";
}

// Raw image data from backend (supports both camelCase and snake_case)
interface RawImageData {
    index?: number;
    data?: string;
    base64_data?: string;
    url?: string;
    storage_key?: string;
    storageKey?: string;
    file_id?: string;
    fileId?: string;
    mime_type?: string;
    mimeType?: string;
}

// Metadata that can come from message (parsed or raw)
interface ParsedMetadata {
    model?: string;
    tokens?: number;
    images?: RawImageData[];
    generated_images?: RawImageData[];
    agentEvents?: AgentEvent[];
}

/**
 * Typing indicator with animated dots
 */
function TypingIndicator({ message }: { message?: string }) {
    const t = useTranslations("chat");
    const displayMessage = message || t("agent.thinking");

    return (
        <div className="flex items-center gap-3 py-2 mb-2">
            <div className="flex items-center gap-1.5 px-3 py-2 bg-muted/50 rounded-full">
                <span
                    className="w-2 h-2 bg-primary/60 rounded-full typing-dot"
                    style={{ animationDelay: "0ms" }}
                />
                <span
                    className="w-2 h-2 bg-primary/60 rounded-full typing-dot"
                    style={{ animationDelay: "200ms" }}
                />
                <span
                    className="w-2 h-2 bg-primary/60 rounded-full typing-dot"
                    style={{ animationDelay: "400ms" }}
                />
            </div>
            <span className="text-sm text-muted-foreground animate-pulse">{displayMessage}</span>
        </div>
    );
}

/**
 * Streaming cursor that blinks at the end of content
 * Uses pure CSS animation to avoid React re-renders
 * Refined for precise alignment and visual polish
 */
function StreamingCursor() {
    return (
        <span
            className="streaming-cursor-wrapper"
            aria-hidden="true"
        >
            <span className="streaming-cursor-bar" />
        </span>
    );
}

/**
 * Loading skeleton with shimmer effect for waiting state
 */
function LoadingSkeleton() {
    return (
        <div className="space-y-3 py-2 animate-pulse">
            <div className="h-4 bg-muted/60 rounded-md w-3/4 shimmer" />
            <div className="h-4 bg-muted/60 rounded-md w-full shimmer" style={{ animationDelay: "150ms" }} />
            <div className="h-4 bg-muted/60 rounded-md w-5/6 shimmer" style={{ animationDelay: "300ms" }} />
        </div>
    );
}

interface MessageBubbleProps {
    message: Message;
    onRegenerate?: () => void;
    isStreaming?: boolean;
    images?: GeneratedImage[]; // For charts and generated images
}

function MessageAttachments({
    attachments,
    onAttachmentClick
}: {
    attachments: FileAttachment[];
    onAttachmentClick?: (attachment: FileAttachment) => void;
}) {
    if (!attachments || attachments.length === 0) return null;

    return (
        <div className="flex flex-wrap gap-2">
            {attachments.map((attachment) => {
                // Handle both camelCase (frontend) and snake_case (backend) formats
                const contentType = attachment.contentType || (attachment as any).content_type || "";
                const isImage = contentType.startsWith("image/");

                return (
                    <button
                        key={attachment.id}
                        onClick={() => onAttachmentClick?.(attachment)}
                        className={cn(
                            "flex items-center gap-2 px-3 py-2",
                            "rounded-lg",
                            "bg-secondary hover:bg-secondary/80",
                            "border border-border",
                            "transition-colors",
                            "text-sm font-medium"
                        )}
                    >
                        {isImage ? (
                            <ImageIcon className="w-4 h-4 text-primary/70" />
                        ) : (
                            <FileText className="w-4 h-4 text-primary/70" />
                        )}
                        <span className="max-w-[180px] truncate text-foreground/90">
                            {attachment.filename}
                        </span>
                    </button>
                );
            })}
        </div>
    );
}

export const MessageBubble = memo(function MessageBubble({ message, onRegenerate, isStreaming = false, images }: MessageBubbleProps) {
    const isUser = message.role === "user";
    const [copied, setCopied] = useState(false);
    const openPreview = usePreviewStore((state) => state.openPreview);
    const t = useTranslations("chat");
    // Strip image placeholders from content - we render images separately now
    const normalizedContent = message.content
        .replace(/!\[generated-image:\d+\]\(placeholder\)/g, "") // Remove full placeholders
        .replace(/!\[generated-image:\d+\]/g, ""); // Remove placeholders without url
    const parsedMetadata: ParsedMetadata | undefined = (() => {
        if (!message.metadata || typeof message.metadata !== "string") {
            return message.metadata as ParsedMetadata | undefined;
        }
        try {
            return JSON.parse(message.metadata) as ParsedMetadata;
        } catch {
            return undefined;
        }
    })();

    // Deduplicate images by index to prevent multiple renders
    const rawImages: RawImageData[] | undefined = images || parsedMetadata?.images || parsedMetadata?.generated_images;


    // Normalize images from various formats (camelCase/snake_case) to consistent structure
    const normalizedImages: NormalizedImage[] | undefined = rawImages?.map((img: RawImageData, idx: number): NormalizedImage => ({
        index: img.index ?? idx,
        data: img.data ?? img.base64_data,
        url: img.url,
        storageKey: img.storageKey ?? img.storage_key,
        fileId: img.fileId ?? img.file_id,
        mimeType: (img.mimeType ?? img.mime_type ?? "image/png") as NormalizedImage["mimeType"],
    }));

    // Filter out duplicate images by index
    const effectiveImages: NormalizedImage[] | undefined = normalizedImages ? (() => {
        const seen = new Set<number>();
        return normalizedImages.filter((img: NormalizedImage) => {
            if (seen.has(img.index)) {
                return false;
            }
            seen.add(img.index);
            return true;
        });
    })() : undefined;


    const handleCopyMessage = async () => {
        await navigator.clipboard.writeText(message.content);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const handleAttachmentClick = (attachment: FileAttachment) => {
        openPreview(attachment);
    };

    return (
        <div
            className={cn(
                "group py-5",
                isUser ? "flex justify-end" : "flex justify-start"
            )}
        >
            {isUser ? (
                <div className="relative max-w-[95%] md:max-w-[80%] animate-in slide-in-from-right-2 fade-in duration-300">
                    <div
                        className={cn(
                            "relative px-5 py-3.5",
                            "bg-card text-foreground",
                            "rounded-xl rounded-br-md",
                            "border border-border"
                        )}
                    >
                        {message.content && (
                            <p className="text-base leading-relaxed whitespace-pre-wrap">
                                {message.content}
                            </p>
                        )}
                        {message.attachments && message.attachments.length > 0 && (
                            <div className={cn(message.content && "mt-3")}>
                                <MessageAttachments
                                    attachments={message.attachments}
                                    onAttachmentClick={handleAttachmentClick}
                                />
                            </div>
                        )}
                    </div>
                </div>
            ) : (
                <div className="max-w-full animate-in slide-in-from-left-2 fade-in duration-300">
                    {/* Assistant header with icon and name */}
                    <div className="flex items-center gap-2.5 mb-4">
                        <div className="w-6 h-6 flex items-center justify-center">
                            <Image
                                src="/images/logo-light.svg"
                                alt="HyperAgent"
                                width={24}
                                height={24}
                                className="dark:hidden transition-opacity duration-200"
                                style={{ opacity: 0.88 }}
                            />
                            <Image
                                src="/images/logo-dark.svg"
                                alt="HyperAgent"
                                width={24}
                                height={24}
                                className="hidden dark:block transition-opacity duration-200"
                                style={{ opacity: 0.9 }}
                            />
                        </div>
                        <span className="text-[15px] font-medium text-foreground tracking-[-0.01em] opacity-90">HyperAgent</span>
                    </div>

                    {/* Show typing indicator when no content yet */}
                    {!message.content && isStreaming && (
                        <TypingIndicator />
                    )}

                    <div
                        className={cn(
                            "prose prose-neutral dark:prose-invert max-w-none",
                            "text-foreground/95",
                            "[&>*:first-child]:mt-0 [&>*:last-child]:mb-0"
                        )}
                    >
                        <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            components={{
                                p: ({ children }) => (
                                    <p className="mb-4 last:mb-0 text-base leading-relaxed text-foreground/90">
                                        {children}
                                    </p>
                                ),
                                ul: ({ children }) => (
                                    <ul className="my-4 ml-1 space-y-2 list-none">
                                        {React.Children.map(children, (child) =>
                                            React.isValidElement(child) ? (
                                                <li className="relative pl-5 text-base leading-relaxed text-foreground/90 before:absolute before:left-0 before:top-[0.6em] before:h-1.5 before:w-1.5 before:rounded-full before:bg-primary/60">
                                                    {child.props.children}
                                                </li>
                                            ) : null
                                        )}
                                    </ul>
                                ),
                                ol: ({ children }) => (
                                    <ol className="my-4 ml-1 space-y-2 list-none">
                                        {React.Children.map(children, (child, index) =>
                                            React.isValidElement(child) ? (
                                                <li className="relative pl-6 text-base leading-relaxed text-foreground/90">
                                                    <span className="absolute left-0 top-0 font-mono text-xs text-muted-foreground tabular-nums">
                                                        {index + 1}.
                                                    </span>
                                                    {child.props.children}
                                                </li>
                                            ) : null
                                        )}
                                    </ol>
                                ),
                                li: ({ children }) => (
                                    <li className="leading-relaxed">{children}</li>
                                ),
                                a: ({ href, children }) => {
                                    // Filter out invalid URLs (e.g., Chinese text being used as URLs)
                                    const isValidUrl = href && (
                                        href.startsWith('http://') ||
                                        href.startsWith('https://') ||
                                        href.startsWith('/') ||
                                        href.startsWith('#')
                                    );

                                    if (!isValidUrl) {
                                        // Render as plain text if URL is invalid
                                        return <span className="text-foreground">{children}</span>;
                                    }

                                    return (
                                        <a
                                            href={href}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="text-accent-blue underline underline-offset-2 hover:text-accent-blue/80 transition-colors"
                                        >
                                            {children}
                                        </a>
                                    );
                                },
                                img: ({ src, alt }) => {
                                    // Generated images are rendered outside ReactMarkdown
                                    // This handler only processes regular markdown images

                                    // Filter out invalid image sources
                                    const isValidSrc = src && (
                                        src.startsWith('http://') ||
                                        src.startsWith('https://') ||
                                        src.startsWith('/') ||
                                        src.startsWith('data:')
                                    );

                                    if (!isValidSrc) {
                                        // Render alt text if src is invalid
                                        return (
                                            <span className="inline-flex items-center gap-2 px-3 py-1.5 bg-secondary rounded text-sm text-muted-foreground">
                                                <ImageIcon className="w-4 h-4" />
                                                {alt || 'Invalid image source'}
                                            </span>
                                        );
                                    }

                                    return (
                                        <img
                                            src={src}
                                            alt={alt || ''}
                                            className="max-w-full h-auto rounded-lg my-4"
                                        />
                                    );
                                },
                                code: ({ node, className, children, ...props }) => {
                                    const match = /language-(\w+)/.exec(className || "");
                                    const isInline = !match;

                                    if (isInline) {
                                        return (
                                            <code className="px-1.5 py-0.5 font-mono text-sm bg-secondary rounded">
                                                {children}
                                            </code>
                                        );
                                    }

                                    return (
                                        <CodeBlock language={match[1]}>
                                            {String(children).replace(/\n$/, "")}
                                        </CodeBlock>
                                    );
                                },
                                blockquote: ({ children }) => (
                                    <blockquote className="my-4 pl-4 border-l-2 border-border text-muted-foreground italic">
                                        {children}
                                    </blockquote>
                                ),
                                h1: ({ children }) => (
                                    <h1 className="mt-6 mb-3 first:mt-0 text-xl font-semibold text-foreground">
                                        {children}
                                    </h1>
                                ),
                                h2: ({ children }) => (
                                    <h2 className="mt-5 mb-2 first:mt-0 text-lg font-semibold text-foreground">
                                        {children}
                                    </h2>
                                ),
                                h3: ({ children }) => (
                                    <h3 className="mt-4 mb-2 first:mt-0 text-base font-medium text-foreground">
                                        {children}
                                    </h3>
                                ),
                                hr: () => <hr className="my-6 border-t border-border" />,
                                strong: ({ children }) => (
                                    <strong className="font-semibold">{children}</strong>
                                ),
                                em: ({ children }) => <em className="italic">{children}</em>,
                                table: ({ children }) => (
                                    <div className="my-4 overflow-x-auto rounded-lg border border-border">
                                        <table className="w-full text-sm">{children}</table>
                                    </div>
                                ),
                                thead: ({ children }) => (
                                    <thead className="bg-secondary/50">{children}</thead>
                                ),
                                tbody: ({ children }) => <tbody>{children}</tbody>,
                                tr: ({ children }) => (
                                    <tr className="border-b border-border last:border-b-0">{children}</tr>
                                ),
                                th: ({ children }) => (
                                    <th className="px-4 py-2.5 text-left font-semibold text-foreground border-r border-border last:border-r-0">
                                        {children}
                                    </th>
                                ),
                                td: ({ children }) => (
                                    <td className="px-4 py-2.5 text-foreground/90 border-r border-border last:border-r-0">
                                        {children}
                                    </td>
                                ),
                            }}
                        >
                            {normalizedContent}
                        </ReactMarkdown>
                        {/* Show streaming cursor at the end of content */}
                        {isStreaming && message.content && <StreamingCursor />}
                    </div>

                    {/* Render images after markdown content */}
                    {/* ReactMarkdown has issues with custom img components, so we render separately */}
                    {effectiveImages && effectiveImages.length > 0 && (
                        <div className="mt-4 space-y-4">
                            {effectiveImages.map((img: NormalizedImage) => (
                                <GeneratedMedia
                                    key={`gallery-img-${img.index}`}
                                    data={img.data}
                                    url={img.url}
                                    mimeType={img.mimeType}
                                />
                            ))}
                        </div>
                    )}

                    {/* DISABLED: Old gallery logic - kept for reference */}
                    {false && !isStreaming && effectiveImages && effectiveImages.length > 0 && (() => {
                        // Filter out images that have inline placeholders in content
                        const inlinePlaceholderIndices = new Set<number>();
                        const placeholderMatches = normalizedContent.matchAll(/!\[generated-image:(\d+)\]/g);
                        for (const match of placeholderMatches) {
                            inlinePlaceholderIndices.add(parseInt(match[1], 10));
                        }
                        // Only show images that don't have inline placeholders
                        const nonInlineImages = effectiveImages.filter((img: NormalizedImage) =>
                            !inlinePlaceholderIndices.has(img.index)
                        );

                        if (nonInlineImages.length === 0) return null;
                        return (
                            <div className="mt-4">
                                {nonInlineImages.map((img: NormalizedImage) => (
                                    <GeneratedMedia
                                        key={`gallery-${img.index}`}
                                        data={img.data}
                                        url={img.url}
                                        mimeType={img.mimeType}
                                    />
                                ))}
                            </div>
                        );
                    })()}

                    {/* Action buttons for assistant message - only show when not streaming */}
                    {!isStreaming && (
                        <div className="mt-3 flex items-center gap-1">
                            <button
                                onClick={handleCopyMessage}
                                className={cn(
                                    "flex items-center gap-1.5",
                                    "px-2.5 py-1.5",
                                    "text-xs font-medium",
                                    "rounded-xl",
                                    "transition-all duration-200",
                                    copied
                                        ? "text-accent-cyan bg-accent-cyan/10"
                                        : "text-muted-foreground hover:text-foreground hover:bg-secondary"
                                )}
                            >
                                {copied ? (
                                    <>
                                        <Check className="w-3.5 h-3.5" strokeWidth={2.5} />
                                        <span>{t("copied")}</span>
                                    </>
                                ) : (
                                    <>
                                        <Copy className="w-3.5 h-3.5" />
                                        <span>{t("copy")}</span>
                                    </>
                                )}
                            </button>

                            {onRegenerate && (
                                <button
                                    onClick={onRegenerate}
                                    className={cn(
                                        "flex items-center gap-1.5",
                                        "px-2.5 py-1.5",
                                        "text-xs font-medium",
                                        "rounded-xl",
                                        "transition-all duration-200",
                                        "text-muted-foreground hover:text-foreground hover:bg-secondary"
                                    )}
                                >
                                    <RotateCcw className="w-3.5 h-3.5" />
                                    <span>{t("regenerate")}</span>
                                </button>
                            )}
                        </div>
                    )}
                </div>
            )}

            {/* File preview is now handled by the layout level via usePreviewStore */}
        </div>
    );
});

interface CodeBlockProps {
    language: string;
    children: string;
}

// Pre-computed code themes with custom overrides
const darkCodeTheme: { [key: string]: React.CSSProperties } = {
    ...oneDark,
    'pre[class*="language-"]': {
        ...oneDark['pre[class*="language-"]'],
        background: "transparent",
        margin: 0,
        padding: 0,
    },
    'code[class*="language-"]': {
        ...oneDark['code[class*="language-"]'],
        background: "transparent",
        fontSize: "13px",
        lineHeight: "1.7",
    },
};

const lightCodeTheme: { [key: string]: React.CSSProperties } = {
    ...oneLight,
    'pre[class*="language-"]': {
        ...oneLight['pre[class*="language-"]'],
        background: "transparent",
        margin: 0,
        padding: 0,
    },
    'code[class*="language-"]': {
        ...oneLight['code[class*="language-"]'],
        background: "transparent",
        fontSize: "13px",
        lineHeight: "1.7",
    },
};

function CodeBlock({ language, children }: CodeBlockProps) {
    const [copied, setCopied] = useState(false);
    const [isHovered, setIsHovered] = useState(false);
    const { resolvedTheme } = useTheme();
    const t = useTranslations("chat");

    const isDark = resolvedTheme === "dark";

    const handleCopy = async () => {
        await navigator.clipboard.writeText(children);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const currentStyle = isDark ? darkCodeTheme : lightCodeTheme;

    return (
        <div
            className={cn(
                "my-5 rounded-xl overflow-hidden",
                "ring-1 transition-all duration-300",
                // Light mode styles
                "bg-secondary ring-border",
                // Dark mode styles (deep black for Cursor aesthetic)
                "dark:bg-card dark:ring-border/50",
                // Hover states
                isHovered && (
                    "ring-foreground/20 dark:ring-border dark:shadow-glow-sm"
                )
            )}
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
        >
            {/* Header */}
            <div
                className={cn(
                    "flex items-center justify-between",
                    "px-3 md:px-4 py-2 md:py-2.5",
                    "border-b border-border",
                    "bg-secondary"
                )}
            >
                <div className="flex items-center gap-2">
                    <div className={cn(
                        "w-5 h-5 rounded flex items-center justify-center",
                        "bg-muted"
                    )}>
                        <Terminal className="w-3 h-3 text-muted-foreground" />
                    </div>
                    <span className="text-xs font-mono text-muted-foreground">
                        {language}
                    </span>
                </div>

                <button
                    onClick={handleCopy}
                    className={cn(
                        "flex items-center gap-1.5",
                        "px-2 py-1 -my-0.5",
                        "text-xs",
                        "rounded",
                        "transition-colors",
                        copied
                            ? "text-foreground bg-secondary"
                            : "text-muted-foreground hover:text-foreground hover:bg-muted"
                    )}
                >
                    {copied ? (
                        <>
                            <Check className="w-3.5 h-3.5" strokeWidth={2.5} />
                            <span>{t("copied")}</span>
                        </>
                    ) : (
                        <>
                            <Copy className="w-3.5 h-3.5" />
                            <span>{t("copy")}</span>
                        </>
                    )}
                </button>
            </div>

            {/* Code Content */}
            <div className="relative p-3 md:p-4 overflow-x-auto">
                <SyntaxHighlighter
                    language={language}
                    style={currentStyle}
                    customStyle={{ background: "transparent", margin: 0, padding: 0 }}
                >
                    {children}
                </SyntaxHighlighter>
            </div>
        </div>
    );
}
