"use client";

import React, { useState, memo, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { useTranslations } from "next-intl";
import Image from "next/image";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark, oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import { Copy, Check, Terminal, RotateCcw, FileText, ImageIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTheme } from "@/lib/hooks/use-theme";
import { usePreviewStore } from "@/lib/stores/preview-store";
import { GeneratedMedia } from "@/components/chat/generated-media";
import { AgentProgressPanel } from "@/components/ui/agent-progress-panel";
import { LiveAgentProgressPanel } from "@/components/chat/live-agent-progress-panel";
import type { Message, FileAttachment, GeneratedImage, AgentEvent, Source } from "@/lib/types";
import type { TimestampedEvent } from "@/lib/stores/agent-progress-store";

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
 * Thinking indicator - clean pill with pulsing dot
 */
function TypingIndicator({ message }: { message?: string }) {
    const t = useTranslations("chat");
    const displayMessage = message || t("agent.thinking");

    return (
        <div className="inline-flex items-center gap-2.5 px-3.5 py-2 mb-3 rounded-full bg-muted/60 border border-border/40">
            <span className="w-2 h-2 rounded-full bg-primary/80 animate-pulse" />
            <span className="text-[13px] font-medium text-muted-foreground">{displayMessage}</span>
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
    streamingEvents?: TimestampedEvent[]; // Live agent events during streaming
    streamingSources?: Source[]; // Live sources during streaming
    agentType?: string; // Agent type for i18n
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


export const MessageBubble = memo(function MessageBubble({ message, onRegenerate, isStreaming = false, images, streamingEvents, streamingSources, agentType }: MessageBubbleProps) {
    const isUser = message.role === "user";
    const [copied, setCopied] = useState(false);
    const openPreview = usePreviewStore((state) => state.openPreview);
    const t = useTranslations("chat");
    
    // Check if progress panel will actually render (has events that create stage groups)
    // The panel returns null if stageGroups.length === 0, so we need to check if events will create groups
    const willProgressPanelRender = useMemo(() => {
        if (!streamingEvents || streamingEvents.length === 0) return false;
        
        // Check if we have events that will create stage groups
        // Stage events create groups (unless hidden)
        // Tool_call events create groups (implicit "processing" if no current group)
        // Browser_action events create groups
        const HIDDEN_STAGES = new Set(["thinking", "routing"]);
        
        for (const event of streamingEvents) {
            if (event.type === "stage") {
                const stageName = event.name;
                if (stageName && !HIDDEN_STAGES.has(stageName)) {
                    return true; // This will create a stage group
                }
            } else if (event.type === "tool_call") {
                return true; // Tool calls create groups (implicit processing if no current group)
            } else if ((event as any).type === "browser_action") {
                return true; // Browser actions create groups
            }
        }
        
        return false;
    }, [streamingEvents]);
    // Strip image placeholders from content - we render images separately now
    const normalizedContent = message.content
        .replace(/!\[generated-image:\d+\]\(placeholder\)/g, "") // Remove full placeholders
        .replace(/!\[generated-image:\d+\]/g, ""); // Remove placeholders without url
    const hasVisibleContent = normalizedContent.trim().length > 0;
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
                <div className="w-full max-w-[95%] md:max-w-[80%] animate-in slide-in-from-left-2 fade-in duration-300">
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
                        <span className="text-[15px] font-bold text-foreground tracking-[-0.01em] opacity-90">HyperAgent</span>
                    </div>

                    {/* Show typing indicator at the very beginning when streaming starts */}
                    {/* It will be replaced by progress panel once it actually renders */}
                    {isStreaming && !hasVisibleContent && !willProgressPanelRender && (
                        <TypingIndicator />
                    )}

                    {/* Show live agent progress inline during streaming - replaces typing indicator */}
                    {isStreaming && willProgressPanelRender && (
                        <LiveAgentProgressPanel
                            events={streamingEvents}
                            sources={streamingSources}
                            isStreaming={isStreaming}
                            agentType={agentType}
                        />
                    )}

                    <div
                        className={cn(
                            "prose prose-neutral dark:prose-invert max-w-none",
                            "text-foreground/95",
                            "[&>*:first-child]:mt-0 [&>*:last-child]:mb-0"
                        )}
                    >
                        {normalizedContent && (
                            <ReactMarkdown
                                remarkPlugins={[remarkGfm, remarkMath]}
                                rehypePlugins={[rehypeKatex]}
                                components={{
                                p: ({ children }) => (
                                    <p className="mb-5 last:mb-0 text-[15px] leading-[1.75] text-foreground/90 tracking-[-0.01em]">
                                        {children}
                                    </p>
                                ),
                                ul: ({ children }) => (
                                    <ul className="my-5 space-y-2.5 list-none">
                                        {children}
                                    </ul>
                                ),
                                ol: ({ children }) => (
                                    <ol className="my-5 space-y-2.5 list-none [counter-reset:list-counter]">
                                        {children}
                                    </ol>
                                ),
                                li: ({ children, node }) => {
                                    // Check if parent is ol or ul by looking at node structure
                                    const isOrdered = node?.position?.start?.line !== undefined &&
                                        (children?.toString().match(/^\d+\./) || false);

                                    return (
                                        <li className="relative pl-6 text-[15px] leading-[1.7] text-foreground/90 [counter-increment:list-counter]">
                                            <span className={cn(
                                                "absolute left-0 top-0 select-none",
                                                "text-muted-foreground/70 font-medium"
                                            )}>
                                                {/* Elegant bullet or number */}
                                                <span className="inline-block w-1.5 h-1.5 mt-[0.6em] rounded-full bg-foreground/25" />
                                            </span>
                                            <span className="block">{children}</span>
                                        </li>
                                    );
                                },
                                a: ({ href, children }) => {
                                    const isValidUrl = href && (
                                        href.startsWith('http://') ||
                                        href.startsWith('https://') ||
                                        href.startsWith('/') ||
                                        href.startsWith('#')
                                    );

                                    if (!isValidUrl) {
                                        return <span className="text-foreground">{children}</span>;
                                    }

                                    return (
                                        <a
                                            href={href}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className={cn(
                                                "relative inline-block font-medium",
                                                "text-foreground",
                                                "after:absolute after:bottom-0 after:left-0 after:right-0",
                                                "after:h-[1px] after:bg-accent-cyan/50",
                                                "hover:after:bg-accent-cyan hover:text-foreground",
                                                "transition-colors"
                                            )}
                                        >
                                            {children}
                                        </a>
                                    );
                                },
                                img: ({ src, alt }) => {
                                    const isValidSrc = src && (
                                        src.startsWith('http://') ||
                                        src.startsWith('https://') ||
                                        src.startsWith('/') ||
                                        src.startsWith('data:')
                                    );

                                    if (!isValidSrc) {
                                        return (
                                            <span className="inline-flex items-center gap-2 px-3 py-2 bg-secondary/50 rounded-lg text-sm text-muted-foreground border border-border/50">
                                                <ImageIcon className="w-4 h-4" />
                                                {alt || 'Image'}
                                            </span>
                                        );
                                    }

                                    return (
                                        <span className="block my-6">
                                            <img
                                                src={src}
                                                alt={alt || ''}
                                                className="max-w-full h-auto rounded-xl shadow-sm"
                                            />
                                            {alt && (
                                                <span className="block mt-2 text-xs text-muted-foreground text-center italic">
                                                    {alt}
                                                </span>
                                            )}
                                        </span>
                                    );
                                },
                                code: ({ node, className, children, ...props }) => {
                                    const match = /language-(\w+)/.exec(className || "");
                                    const isInline = !match;

                                    if (isInline) {
                                        return (
                                            <code className={cn(
                                                "px-1.5 py-0.5 mx-0.5",
                                                "font-mono text-[0.875em]",
                                                "bg-secondary/80 dark:bg-secondary",
                                                "rounded-md",
                                                "text-foreground/90",
                                                "border border-border/40"
                                            )}>
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
                                    <blockquote className={cn(
                                        "my-6 py-4 px-5",
                                        "border-l-[3px] border-accent-cyan/40",
                                        "bg-secondary/30 dark:bg-secondary/20",
                                        "rounded-r-lg",
                                        "text-foreground/80 italic",
                                        "[&>p]:mb-0 [&>p]:text-[15px]"
                                    )}>
                                        {children}
                                    </blockquote>
                                ),
                                h1: ({ children }) => (
                                    <h1 className={cn(
                                        "mt-8 mb-4 first:mt-0",
                                        "text-xl font-semibold tracking-tight",
                                        "text-foreground",
                                        "flex items-center gap-3"
                                    )}>
                                        <span className="w-1 h-5 bg-primary/80 rounded-full shrink-0" />
                                        {children}
                                    </h1>
                                ),
                                h2: ({ children }) => (
                                    <h2 className={cn(
                                        "mt-7 mb-3 first:mt-0",
                                        "text-lg font-semibold tracking-tight",
                                        "text-foreground"
                                    )}>
                                        {children}
                                    </h2>
                                ),
                                h3: ({ children }) => (
                                    <h3 className={cn(
                                        "mt-6 mb-2.5 first:mt-0",
                                        "text-base font-semibold",
                                        "text-foreground/95"
                                    )}>
                                        {children}
                                    </h3>
                                ),
                                hr: () => (
                                    <hr className="my-8 border-0 h-px bg-gradient-to-r from-transparent via-border to-transparent" />
                                ),
                                strong: ({ children }) => (
                                    <strong className="font-semibold text-foreground">{children}</strong>
                                ),
                                em: ({ children }) => (
                                    <em className="italic text-foreground/85">{children}</em>
                                ),
                                table: ({ children }) => (
                                    <div className="my-6 overflow-x-auto rounded-xl border border-border/80 bg-card">
                                        <table className="w-full text-sm">{children}</table>
                                    </div>
                                ),
                                thead: ({ children }) => (
                                    <thead className="bg-secondary/60 dark:bg-secondary/40">{children}</thead>
                                ),
                                tbody: ({ children }) => (
                                    <tbody className="divide-y divide-border/50">{children}</tbody>
                                ),
                                tr: ({ children }) => (
                                    <tr className="hover:bg-secondary/30 transition-colors">{children}</tr>
                                ),
                                th: ({ children }) => (
                                    <th className={cn(
                                        "px-4 py-3",
                                        "text-left text-xs font-semibold uppercase tracking-wider",
                                        "text-muted-foreground"
                                    )}>
                                        {children}
                                    </th>
                                ),
                                td: ({ children }) => (
                                    <td className="px-4 py-3 text-foreground/85">
                                        {children}
                                    </td>
                                ),
                            }}
                            >
                                {normalizedContent}
                            </ReactMarkdown>
                        )}
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

                    {/* Show saved agent events (progress steps) if available - only when not streaming */}
                    {!isStreaming && parsedMetadata?.agentEvents && parsedMetadata.agentEvents.length > 0 && (
                        <AgentProgressPanel events={parsedMetadata.agentEvents} />
                    )}

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
}, (prevProps, nextProps) => {
    // During streaming, always re-render to show updates
    if (nextProps.isStreaming || prevProps.isStreaming) {
        return false; // Re-render
    }
    // For non-streaming messages, use default shallow comparison
    return (
        prevProps.message.id === nextProps.message.id &&
        prevProps.message.content === nextProps.message.content &&
        prevProps.message.role === nextProps.message.role &&
        prevProps.isStreaming === nextProps.isStreaming &&
        prevProps.images === nextProps.images &&
        prevProps.streamingEvents === nextProps.streamingEvents &&
        prevProps.streamingSources === nextProps.streamingSources
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
        lineHeight: "1.65",
        fontFamily: 'ui-monospace, "SF Mono", SFMono-Regular, Menlo, Monaco, Consolas, monospace',
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
        lineHeight: "1.65",
        fontFamily: 'ui-monospace, "SF Mono", SFMono-Regular, Menlo, Monaco, Consolas, monospace',
    },
};

// Language display names and colors
const LANGUAGE_CONFIG: Record<string, { name: string; color: string }> = {
    javascript: { name: "JavaScript", color: "hsl(50, 90%, 50%)" },
    js: { name: "JavaScript", color: "hsl(50, 90%, 50%)" },
    typescript: { name: "TypeScript", color: "hsl(211, 60%, 48%)" },
    ts: { name: "TypeScript", color: "hsl(211, 60%, 48%)" },
    python: { name: "Python", color: "hsl(207, 51%, 44%)" },
    py: { name: "Python", color: "hsl(207, 51%, 44%)" },
    rust: { name: "Rust", color: "hsl(25, 83%, 53%)" },
    go: { name: "Go", color: "hsl(192, 68%, 46%)" },
    java: { name: "Java", color: "hsl(15, 80%, 50%)" },
    cpp: { name: "C++", color: "hsl(210, 55%, 50%)" },
    c: { name: "C", color: "hsl(210, 55%, 45%)" },
    html: { name: "HTML", color: "hsl(14, 77%, 52%)" },
    css: { name: "CSS", color: "hsl(228, 77%, 52%)" },
    json: { name: "JSON", color: "hsl(0, 0%, 50%)" },
    yaml: { name: "YAML", color: "hsl(0, 0%, 55%)" },
    bash: { name: "Bash", color: "hsl(120, 15%, 45%)" },
    shell: { name: "Shell", color: "hsl(120, 15%, 45%)" },
    sql: { name: "SQL", color: "hsl(210, 50%, 50%)" },
    markdown: { name: "Markdown", color: "hsl(0, 0%, 45%)" },
    md: { name: "Markdown", color: "hsl(0, 0%, 45%)" },
    jsx: { name: "JSX", color: "hsl(193, 95%, 50%)" },
    tsx: { name: "TSX", color: "hsl(211, 60%, 48%)" },
    swift: { name: "Swift", color: "hsl(15, 100%, 55%)" },
    kotlin: { name: "Kotlin", color: "hsl(270, 65%, 55%)" },
    ruby: { name: "Ruby", color: "hsl(0, 65%, 50%)" },
    php: { name: "PHP", color: "hsl(240, 35%, 55%)" },
};

function CodeBlock({ language, children }: CodeBlockProps) {
    const [copied, setCopied] = useState(false);
    const { resolvedTheme } = useTheme();
    const t = useTranslations("chat");

    const isDark = resolvedTheme === "dark";
    const langConfig = LANGUAGE_CONFIG[language.toLowerCase()] || { name: language, color: "hsl(var(--muted-foreground))" };

    const handleCopy = async () => {
        await navigator.clipboard.writeText(children);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const currentStyle = isDark ? darkCodeTheme : lightCodeTheme;
    const lineCount = children.split('\n').length;

    return (
        <div
            className={cn(
                "group/code my-6 rounded-xl overflow-hidden",
                "border border-border/60",
                "bg-[hsl(0,0%,97%)] dark:bg-[hsl(0,0%,8%)]",
                "shadow-sm hover:shadow-md",
                "transition-shadow duration-200"
            )}
        >
            {/* Header - refined with language indicator */}
            <div
                className={cn(
                    "flex items-center justify-between",
                    "px-4 py-2.5",
                    "border-b border-border/40",
                    "bg-secondary/50 dark:bg-secondary/30"
                )}
            >
                <div className="flex items-center gap-3">
                    {/* Language indicator dot */}
                    <div className="flex items-center gap-2">
                        <span
                            className="w-2.5 h-2.5 rounded-full shrink-0"
                            style={{ backgroundColor: langConfig.color }}
                        />
                        <span className="text-xs font-medium text-muted-foreground tracking-wide">
                            {langConfig.name}
                        </span>
                    </div>
                    {/* Line count badge */}
                    <span className="text-[10px] text-muted-foreground/60 tabular-nums">
                        {lineCount} {lineCount === 1 ? 'line' : 'lines'}
                    </span>
                </div>

                {/* Copy button with improved feedback */}
                <button
                    onClick={handleCopy}
                    className={cn(
                        "flex items-center gap-1.5",
                        "px-2.5 py-1",
                        "text-xs font-medium",
                        "rounded-md",
                        "transition-all duration-150",
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
                            <Copy className="w-3.5 h-3.5 opacity-70 group-hover/code:opacity-100 transition-opacity" />
                            <span className="opacity-0 group-hover/code:opacity-100 transition-opacity">{t("copy")}</span>
                        </>
                    )}
                </button>
            </div>

            {/* Code Content with subtle line numbers area */}
            <div className="relative overflow-x-auto">
                <div className="p-4">
                    <SyntaxHighlighter
                        language={language}
                        style={currentStyle}
                        customStyle={{
                            background: "transparent",
                            margin: 0,
                            padding: 0,
                        }}
                        codeTagProps={{
                            style: {
                                fontFamily: 'ui-monospace, "SF Mono", SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                            }
                        }}
                    >
                        {children}
                    </SyntaxHighlighter>
                </div>
            </div>
        </div>
    );
}
