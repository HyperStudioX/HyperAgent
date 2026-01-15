"use client";

import React, { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Copy, Check, BookOpen, FileText, List, ChevronRight } from "lucide-react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
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

export function ResearchResultView({ content, isStreaming = false, title = "Analysis Report" }: ResearchResultViewProps) {
    const [toc, setToc] = useState<TocItem[]>([]);
    const [isTocCollapsed, setIsTocCollapsed] = useState(false);

    // Extract headings for Table of Contents
    useEffect(() => {
        const headings = content.match(/^#{1,3}\s+.+$/gm) || [];
        const tocItems = headings.map((h) => {
            const level = (h.match(/^#+/) || [""])[0].length;
            const text = h.replace(/^#+\s+/, "");
            const id = text.toLowerCase().replace(/[^\w\s-]/g, "").replace(/\s+/g, "-");
            return { id, text, level };
        });
        setToc(tocItems);
    }, [content]);

    return (
        <div className="flex flex-col lg:flex-row gap-8 relative w-full px-4 md:px-0">
            {/* Sidebar TOC - Visible on Large Screens */}
            {toc.length > 0 && (
                <aside
                    className={cn(
                        "hidden lg:block shrink-0 h-fit sticky top-24 transition-all duration-300 ease-in-out border-r border-transparent",
                        isTocCollapsed ? "w-12" : "w-64"
                    )}
                >
                    <div className="flex items-center justify-between mb-4 px-2">
                        {!isTocCollapsed && (
                            <div className="flex items-center gap-2 text-foreground font-semibold text-xs uppercase tracking-wider animate-in fade-in duration-300">
                                <List className="w-4 h-4" />
                                <span>Table of Contents</span>
                            </div>
                        )}
                        <button
                            onClick={() => setIsTocCollapsed(!isTocCollapsed)}
                            className="p-1.5 hover:bg-secondary/50 rounded-md text-muted-foreground hover:text-foreground transition-colors ml-auto"
                            title={isTocCollapsed ? "Expand outline" : "Collapse outline"}
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
                    <div className="bg-card border border-border rounded-xl overflow-hidden">
                        {/* Content Body */}
                        <div className="px-6 py-10 md:px-10 md:py-12">
                            <div className="prose prose-sm md:prose-base max-w-none text-foreground font-sans">
                                <ReactMarkdown
                                    remarkPlugins={[remarkGfm]}
                                    components={{
                                        h1: ({ children }) => {
                                            const id = String(children).toLowerCase().replace(/[^\w\s-]/g, "").replace(/\s+/g, "-");
                                            return (
                                                <h1 id={id} className="text-2xl font-bold mt-12 mb-6 first:mt-0 text-foreground flex items-center gap-3 scroll-mt-24">
                                                    <div className="w-1.5 h-6 bg-primary rounded-full" />
                                                    <span>{children}</span>
                                                </h1>
                                            );
                                        },
                                        h2: ({ children }) => {
                                            const id = String(children).toLowerCase().replace(/[^\w\s-]/g, "").replace(/\s+/g, "-");
                                            return (
                                                <h2 id={id} className="text-xl font-semibold mt-10 mb-5 first:mt-0 text-foreground flex items-center gap-2 scroll-mt-24 border-b border-border pb-2">
                                                    <FileText className="w-5 h-5 text-muted-foreground shrink-0" />
                                                    <span className="flex-1">{children}</span>
                                                </h2>
                                            );
                                        },
                                        h3: ({ children }) => {
                                            const id = String(children).toLowerCase().replace(/[^\w\s-]/g, "").replace(/\s+/g, "-");
                                            return (
                                                <h3 id={id} className="text-lg font-semibold mt-8 mb-4 first:mt-0 text-foreground flex items-center gap-2 scroll-mt-24">
                                                    <ChevronRight className="w-4 h-4 text-muted-foreground" />
                                                    <span>{children}</span>
                                                </h3>
                                            );
                                        },
                                        p: ({ children }) => (
                                            <p className="mb-6 last:mb-0 leading-relaxed text-base text-foreground/90">
                                                {children}
                                            </p>
                                        ),
                                        ul: ({ children }) => (
                                            <ul className="list-none pl-2 mb-6 space-y-3">
                                                {children}
                                            </ul>
                                        ),
                                        ol: ({ children }) => (
                                            <ol className="list-none pl-2 mb-6 space-y-3 [counter-reset:step-counter]">
                                                {children}
                                            </ol>
                                        ),
                                        li: ({ children, ...props }) => {
                                            const isOrdered = (props as any).node?.tagName === 'ol' || (props as any).ordered;
                                            return (
                                                <li className="flex gap-3 leading-relaxed text-foreground/90 text-sm md:text-base">
                                                    {isOrdered ? (
                                                        <span className="flex-none font-bold text-foreground tabular-nums [counter-increment:step-counter] after:content-[counter(step-counter)'.'] min-w-[1.25rem]" />
                                                    ) : (
                                                        <div className="mt-2.5 flex-none w-1.5 h-1.5 rounded-full bg-foreground/30" />
                                                    )}
                                                    <div className="flex-1">{children}</div>
                                                </li>
                                            );
                                        },
                                        blockquote: ({ children }) => (
                                            <blockquote className="border-l-4 border-border pl-6 pr-4 py-4 my-8 bg-secondary/30 rounded-r-lg italic text-muted-foreground">
                                                <div className="leading-relaxed text-base md:text-lg">{children}</div>
                                            </blockquote>
                                        ),
                                        code: ({ node, className, children, ...props }: any) => {
                                            const match = /language-(\w+)/.exec(className || "");
                                            const isInline = !match;

                                            if (isInline) {
                                                return (
                                                    <code className="bg-muted px-1.5 py-0.5 rounded-md text-[0.85em] font-mono font-medium text-foreground border border-border">
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
                                            <hr className="my-10 border-t border-border" />
                                        ),
                                        table: ({ children }) => (
                                            <div className="overflow-x-auto my-8 rounded-lg border border-border bg-card">
                                                <table className="min-w-full divide-y divide-border">
                                                    {children}
                                                </table>
                                            </div>
                                        ),
                                        thead: ({ children }) => (
                                            <thead className="bg-secondary/50">{children}</thead>
                                        ),
                                        th: ({ children }) => (
                                            <th className="px-4 py-3 text-left text-xs font-semibold text-foreground uppercase tracking-wider border-b border-border">
                                                {children}
                                            </th>
                                        ),
                                        td: ({ children }) => (
                                            <td className="px-4 py-3 text-sm text-foreground/80 border-b border-border/50">
                                                {children}
                                            </td>
                                        ),
                                        strong: ({ children }) => (
                                            <strong className="font-bold text-foreground">{children}</strong>
                                        ),
                                        a: ({ href, children }) => (
                                            <a
                                                href={href}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="text-foreground font-medium underline decoration-border underline-offset-4 hover:decoration-foreground transition-colors px-0.5"
                                            >
                                                {children}
                                            </a>
                                        ),
                                    }}
                                >
                                    {content}
                                </ReactMarkdown>

                                {isStreaming && (
                                    <div className="mt-10 flex flex-col gap-3 p-6 rounded-xl bg-secondary/20 border border-border border-dashed">
                                        <div className="flex items-center gap-3 text-muted-foreground font-medium">
                                            <div className="flex gap-1">
                                                <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-pulse" />
                                                <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-pulse [animation-delay:0.2s]" />
                                                <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-pulse [animation-delay:0.4s]" />
                                            </div>
                                            <span className="text-xs tracking-widest uppercase">Refining analysis...</span>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Footer Metadata */}
                    <div className="mt-8 flex flex-wrap items-center justify-between gap-4 text-muted-foreground text-xs font-medium px-2 uppercase tracking-widest border-t border-border/50 pt-6">
                        <div className="flex items-center gap-4">
                            <span>HyperAgent Synthetic</span>
                            <span className="w-1 h-1 rounded-full bg-border" />
                            <span>v0.1.0</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <BookOpen className="w-3.5 h-3.5" />
                            <span>Verified Report</span>
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

function CodeBlock({ language, children }: CodeBlockProps) {
    const [copied, setCopied] = useState(false);

    const handleCopy = async () => {
        await navigator.clipboard.writeText(children);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="my-8 rounded-xl overflow-hidden border border-border bg-muted">
            <div className="flex items-center justify-between bg-secondary px-5 py-3 border-b border-border">
                <div className="flex items-center gap-3">
                    <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">
                        {language || "code"}
                    </span>
                </div>
                <button
                    onClick={handleCopy}
                    className="flex items-center gap-2 px-3 py-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                    {copied ? (
                        <Check className="w-3.5 h-3.5 text-foreground" />
                    ) : (
                        <Copy className="w-3.5 h-3.5" />
                    )}
                    <span className="font-medium">
                        {copied ? "Copied" : "Copy"}
                    </span>
                </button>
            </div>
            <div className="relative overflow-x-auto">
                <SyntaxHighlighter
                    language={language || "text"}
                    style={vscDarkPlus}
                    customStyle={{
                        margin: 0,
                        padding: "1.25rem",
                        fontSize: "13px",
                        lineHeight: "1.6",
                        background: "transparent",
                    }}
                    codeTagProps={{
                        style: {
                            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                        }
                    }}
                >
                    {children}
                </SyntaxHighlighter>
            </div>
        </div>
    );
}
