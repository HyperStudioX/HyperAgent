"use client";

import React, { useState, useMemo, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { BookOpen, List, ChevronRight } from "lucide-react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";

interface ResearchResultViewProps {
    content: string;
    isStreaming?: boolean;
    title?: string;
}

interface TocItem {
    id: string;
    text: string;
    level: number;
}

// Memoized heading extraction function
const extractHeadings = (content: string): TocItem[] => {
    const headings = content.match(/^#{1,3}\s+.+$/gm) || [];
    return headings.map((h) => {
        const level = (h.match(/^#+/) || [""])[0].length;
        const text = h.replace(/^#+\s+/, "");
        const id = text.toLowerCase().replace(/[^\w\s-]/g, "").replace(/\s+/g, "-");
        return { id, text, level };
    });
};

export function ResearchResultView({ content, isStreaming = false, title }: ResearchResultViewProps) {
    const t = useTranslations("report");
    const [isTocCollapsed, setIsTocCollapsed] = useState(false);
    const [debouncedToc, setDebouncedToc] = useState<TocItem[]>([]);
    const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);
    const lastTocLengthRef = useRef(0);
    
    const reportTitle = title || t("defaultTitle");

    // Extract headings with useMemo for non-streaming content
    // During streaming, we debounce updates to prevent excessive re-renders
    const extractedToc = useMemo(() => extractHeadings(content), [content]);

    // Debounced TOC update during streaming
    useEffect(() => {
        // If not streaming, update immediately
        if (!isStreaming) {
            if (debounceTimerRef.current) {
                clearTimeout(debounceTimerRef.current);
                debounceTimerRef.current = null;
            }
            setDebouncedToc(extractedToc);
            lastTocLengthRef.current = extractedToc.length;
            return;
        }

        // During streaming, only update if new headings were added
        // This avoids expensive updates on every token
        if (extractedToc.length === lastTocLengthRef.current) {
            return;
        }

        // Clear existing timer
        if (debounceTimerRef.current) {
            clearTimeout(debounceTimerRef.current);
        }

        // Debounce TOC updates during streaming (200ms)
        debounceTimerRef.current = setTimeout(() => {
            setDebouncedToc(extractedToc);
            lastTocLengthRef.current = extractedToc.length;
        }, 200);

        return () => {
            if (debounceTimerRef.current) {
                clearTimeout(debounceTimerRef.current);
            }
        };
    }, [extractedToc, isStreaming]);

    // Use debounced TOC for rendering
    const toc = debouncedToc;

    return (
        <div className="flex flex-col lg:flex-row gap-8 relative w-full px-4 md:px-0">
            {/* Sidebar TOC - Visible on Large Screens */}
            {toc.length > 0 && (
                <aside
                    className={cn(
                        "hidden lg:block shrink-0 h-fit sticky top-10 md:top-12 transition-all duration-300 ease-in-out border-r border-transparent",
                        isTocCollapsed ? "w-12" : "w-64"
                    )}
                >
                    <div className="flex items-center justify-between mb-4 px-2">
                        {!isTocCollapsed && (
                            <div className="flex items-center gap-2 text-foreground font-semibold text-xs uppercase tracking-wider animate-in fade-in duration-300">
                                <List className="w-4 h-4" />
                                <span>{t("tableOfContents")}</span>
                            </div>
                        )}
                        <button
                            onClick={() => setIsTocCollapsed(!isTocCollapsed)}
                            className="p-1.5 hover:bg-secondary/50 rounded-md text-muted-foreground hover:text-foreground transition-colors ml-auto"
                            title={isTocCollapsed ? t("expandOutline") : t("collapseOutline")}
                        >
                            <ChevronRight className={cn("w-4 h-4 transition-transform duration-300", isTocCollapsed ? "" : "rotate-180")} />
                        </button>
                    </div>

                    {!isTocCollapsed && (
                        <nav className="space-y-1 border-l border-border ml-2 animate-in fade-in duration-300">
                            {toc.map((item, index) => (
                                <a
                                    key={`${item.id}-${item.level}-${index}`}
                                    href={`#${item.id}`}
                                    className={cn(
                                        "block py-2 px-4 text-sm transition-colors hover:bg-secondary/50 border-l-2 -ml-[1px]",
                                        item.level === 1 ? "font-medium border-transparent text-foreground" : "text-muted-foreground border-transparent",
                                        item.level === 2 && "pl-6",
                                        item.level === 3 && "pl-8 text-xs"
                                    )}
                                >
                                    {item.text}
                                </a>
                            ))}
                        </nav>
                    )}
                </aside>
            )}

            {/* Main Report Area */}
            <div className="flex-1 min-w-0">
                <div className="animate-fade-in">
                    {/* Main Container */}
                    <div className="bg-card border border-border rounded-2xl overflow-hidden">
                        {/* Content Body */}
                        <div className="px-6 py-10 md:px-10 md:py-12">
                            <div className="prose prose-sm md:prose-base max-w-none text-foreground font-sans">
                                {content && (
                                    <ReactMarkdown
                                        remarkPlugins={[remarkGfm, remarkMath]}
                                        rehypePlugins={[rehypeKatex]}
                                        components={{
                                        h1: ({ children }) => {
                                            const id = String(children).toLowerCase().replace(/[^\w\s-]/g, "").replace(/\s+/g, "-");
                                            return (
                                                <h1 id={id} className={cn(
                                                    "mt-14 mb-6 first:mt-0",
                                                    "text-2xl md:text-[1.75rem] font-bold tracking-tight",
                                                    "text-foreground",
                                                    "flex items-start gap-4 scroll-mt-24"
                                                )}>
                                                    <span className="w-1 h-7 mt-1 bg-accent-cyan rounded-full shrink-0" />
                                                    <span className="flex-1">{children}</span>
                                                </h1>
                                            );
                                        },
                                        h2: ({ children }) => {
                                            const id = String(children).toLowerCase().replace(/[^\w\s-]/g, "").replace(/\s+/g, "-");
                                            return (
                                                <h2 id={id} className={cn(
                                                    "mt-12 mb-5 first:mt-0",
                                                    "text-xl md:text-[1.35rem] font-semibold tracking-tight",
                                                    "text-foreground",
                                                    "pb-3 border-b border-border/60",
                                                    "scroll-mt-24"
                                                )}>
                                                    {children}
                                                </h2>
                                            );
                                        },
                                        h3: ({ children }) => {
                                            const id = String(children).toLowerCase().replace(/[^\w\s-]/g, "").replace(/\s+/g, "-");
                                            return (
                                                <h3 id={id} className={cn(
                                                    "mt-10 mb-4 first:mt-0",
                                                    "text-lg font-semibold",
                                                    "text-foreground",
                                                    "scroll-mt-24"
                                                )}>
                                                    {children}
                                                </h3>
                                            );
                                        },
                                        p: ({ children }) => (
                                            <p className="mb-6 last:mb-0 text-[15px] md:text-base leading-[1.8] text-foreground/85 tracking-[-0.01em]">
                                                {children}
                                            </p>
                                        ),
                                        ul: ({ children }) => (
                                            <ul className="my-6 space-y-3 list-none">
                                                {children}
                                            </ul>
                                        ),
                                        ol: ({ children }) => (
                                            <ol className="my-6 space-y-3 list-none [counter-reset:report-counter]">
                                                {children}
                                            </ol>
                                        ),
                                        li: ({ children, node }) => {
                                            // Determine if this is in an ordered list by checking parent
                                            const parentTagName = (node as any)?.parentNode?.tagName;
                                            const isOrdered = parentTagName === 'ol';

                                            return (
                                                <li className={cn(
                                                    "relative pl-7",
                                                    "text-[15px] md:text-base leading-[1.75]",
                                                    "text-foreground/85",
                                                    isOrdered && "[counter-increment:report-counter]"
                                                )}>
                                                    <span className="absolute left-0 top-0 select-none text-muted-foreground/60">
                                                        {isOrdered ? (
                                                            <span className="font-semibold tabular-nums text-sm before:content-[counter(report-counter)] after:content-['.']" />
                                                        ) : (
                                                            <span className="inline-block w-1.5 h-1.5 mt-[0.65em] rounded-full bg-accent-cyan/50" />
                                                        )}
                                                    </span>
                                                    <span className="block">{children}</span>
                                                </li>
                                            );
                                        },
                                        blockquote: ({ children }) => (
                                            <blockquote className={cn(
                                                "my-8 py-5 px-6",
                                                "border-l-[3px] border-accent-cyan/50",
                                                "bg-secondary/20 dark:bg-secondary/10",
                                                "rounded-r-xl",
                                                "[&>p]:mb-0 [&>p]:text-foreground/75 [&>p]:italic [&>p]:text-base"
                                            )}>
                                                {children}
                                            </blockquote>
                                        ),
                                        code: ({ node, className, children, ...props }: any) => {
                                            const match = /language-(\w+)/.exec(className || "");
                                            const isInline = !match;

                                            if (isInline) {
                                                return (
                                                    <code className={cn(
                                                        "px-1.5 py-0.5 mx-0.5",
                                                        "font-mono text-[0.85em] font-medium",
                                                        "bg-secondary/60 dark:bg-secondary/40",
                                                        "text-foreground/90",
                                                        "rounded-md border border-border/50"
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
                                        hr: () => (
                                            <hr className="my-12 border-0 h-px bg-gradient-to-r from-transparent via-border to-transparent" />
                                        ),
                                        table: ({ children }) => (
                                            <div className={cn(
                                                "overflow-x-auto my-8",
                                                "rounded-xl border border-border/60",
                                                "bg-card"
                                            )}>
                                                <table className="min-w-full">
                                                    {children}
                                                </table>
                                            </div>
                                        ),
                                        thead: ({ children }) => (
                                            <thead className="bg-secondary/40 dark:bg-secondary/20">{children}</thead>
                                        ),
                                        tbody: ({ children }) => (
                                            <tbody className="divide-y divide-border/40">{children}</tbody>
                                        ),
                                        tr: ({ children }) => (
                                            <tr className="hover:bg-secondary/20 transition-colors">{children}</tr>
                                        ),
                                        th: ({ children }) => (
                                            <th className={cn(
                                                "px-5 py-3.5",
                                                "text-left text-xs font-semibold uppercase tracking-wider",
                                                "text-muted-foreground"
                                            )}>
                                                {children}
                                            </th>
                                        ),
                                        td: ({ children }) => (
                                            <td className="px-5 py-3.5 text-sm text-foreground/80">
                                                {children}
                                            </td>
                                        ),
                                        strong: ({ children }) => (
                                            <strong className="font-semibold text-foreground">{children}</strong>
                                        ),
                                        em: ({ children }) => (
                                            <em className="italic text-foreground/80">{children}</em>
                                        ),
                                        a: ({ href, children }) => (
                                            <a
                                                href={href}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className={cn(
                                                    "relative font-medium text-foreground",
                                                    "after:absolute after:bottom-0 after:left-0 after:right-0",
                                                    "after:h-[1px] after:bg-accent-cyan/50",
                                                    "hover:after:bg-accent-cyan",
                                                    "transition-colors"
                                                )}
                                            >
                                                {children}
                                            </a>
                                        ),
                                    }}
                                    >
                                        {content}
                                    </ReactMarkdown>
                                )}

                                {isStreaming && (
                                    <div className="mt-10 flex flex-col gap-3 p-6 rounded-xl bg-secondary/20 border border-border border-dashed">
                                        <div className="flex items-center gap-3 text-muted-foreground font-medium">
                                            <div className="flex gap-1">
                                                <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-pulse" />
                                                <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-pulse [animation-delay:0.2s]" />
                                                <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-pulse [animation-delay:0.4s]" />
                                            </div>
                                            <span className="text-xs tracking-widest uppercase">{t("refiningAnalysis")}</span>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Footer Metadata */}
                    <div className="mt-8 flex flex-wrap items-center justify-between gap-4 text-muted-foreground text-xs font-medium px-2 uppercase tracking-widest border-t border-border/50 pt-6">
                        <div className="flex items-center gap-4">
                            <span>{t("synthetic")}</span>
                            <span className="w-1 h-1 rounded-full bg-border" />
                            <span>v0.1.0</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <BookOpen className="w-3.5 h-3.5" />
                            <span>{t("verifiedReport")}</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

interface CodeBlockProps {
    language: string;
    children: string;
}

// Language display names - using semantic colors from design system
const LANGUAGE_CONFIG: Record<string, { name: string }> = {
    javascript: { name: "JavaScript" },
    js: { name: "JavaScript" },
    typescript: { name: "TypeScript" },
    ts: { name: "TypeScript" },
    python: { name: "Python" },
    py: { name: "Python" },
    rust: { name: "Rust" },
    go: { name: "Go" },
    java: { name: "Java" },
    cpp: { name: "C++" },
    c: { name: "C" },
    html: { name: "HTML" },
    css: { name: "CSS" },
    json: { name: "JSON" },
    yaml: { name: "YAML" },
    bash: { name: "Bash" },
    shell: { name: "Shell" },
    sql: { name: "SQL" },
    markdown: { name: "Markdown" },
    md: { name: "Markdown" },
    jsx: { name: "JSX" },
    tsx: { name: "TSX" },
};

function CodeBlock({ language, children }: CodeBlockProps) {
    const t = useTranslations("report");
    const langConfig = LANGUAGE_CONFIG[language?.toLowerCase()] || { name: language || t("code") };
    const lineCount = children.split('\n').length;

    return (
        <div className={cn(
            "group my-8 rounded-xl overflow-hidden",
            "border border-border/60 hover:border-border",
            "bg-secondary/30 dark:bg-secondary/20",
            "transition-colors duration-150"
        )}>
            {/* Header with language indicator */}
            <div className={cn(
                "flex items-center justify-between",
                "px-5 py-3",
                "border-b border-border/40",
                "bg-secondary/50 dark:bg-secondary/30"
            )}>
                <div className="flex items-center gap-3">
                    <span className="w-2.5 h-2.5 rounded-full shrink-0 bg-primary/60" />
                    <span className="text-xs font-medium text-muted-foreground tracking-wide">
                        {langConfig.name}
                    </span>
                    <span className="text-[10px] text-muted-foreground/50 tabular-nums">
                        {lineCount} {lineCount === 1 ? 'line' : 'lines'}
                    </span>
                </div>
            </div>

            {/* Code content */}
            <div className="relative overflow-x-auto">
                <SyntaxHighlighter
                    language={language || "text"}
                    style={vscDarkPlus}
                    customStyle={{
                        margin: 0,
                        padding: "1.25rem",
                        fontSize: "13px",
                        lineHeight: "1.65",
                        background: "transparent",
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
    );
}
