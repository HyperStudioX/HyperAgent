"use client";

import type { Components } from "react-markdown";
import { ImageIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { CodeBlock } from "./code-block";

/**
 * Check if a URL is valid for rendering
 */
function isValidUrl(url: string | undefined): boolean {
    if (!url) return false;
    return (
        url.startsWith("http://") ||
        url.startsWith("https://") ||
        url.startsWith("/") ||
        url.startsWith("#")
    );
}

/**
 * Check if an image source is valid for rendering
 */
function isValidImageSrc(src: string | undefined): boolean {
    if (!src) return false;
    return (
        src.startsWith("http://") ||
        src.startsWith("https://") ||
        src.startsWith("/") ||
        src.startsWith("data:")
    );
}

/**
 * Custom React Markdown components for message rendering
 * Provides consistent styling for all markdown elements
 */
export const markdownComponents: Components = {
    p: ({ children }) => (
        <p className="mb-5 last:mb-0 text-[15px] leading-[1.75] text-foreground/90 tracking-[-0.01em]">
            {children}
        </p>
    ),
    ul: ({ children }) => (
        <ul className="my-5 space-y-2.5 list-none">{children}</ul>
    ),
    ol: ({ children }) => (
        <ol className="my-5 space-y-2.5 list-none [counter-reset:list-counter]">
            {children}
        </ol>
    ),
    li: ({ children }) => (
        <li className="relative pl-6 text-[15px] leading-[1.7] text-foreground/90 [counter-increment:list-counter]">
            <span
                className={cn(
                    "absolute left-0 top-0 select-none",
                    "text-muted-foreground/70 font-medium"
                )}
            >
                <span className="inline-block w-1.5 h-1.5 mt-[0.6em] rounded-full bg-foreground/25" />
            </span>
            <span className="block">{children}</span>
        </li>
    ),
    a: ({ href, children }) => {
        if (!isValidUrl(href)) {
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
        if (!isValidImageSrc(src)) {
            return (
                <span className="inline-flex items-center gap-2 px-3 py-2 bg-secondary/50 rounded-lg text-sm text-muted-foreground border border-border/50">
                    <ImageIcon className="w-4 h-4" />
                    {alt || "Image"}
                </span>
            );
        }

        return (
            <span className="block my-6">
                {/* eslint-disable-next-line @next/next/no-img-element -- Dynamic markdown content requires native img */}
                <img
                    src={src}
                    alt={alt || ""}
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
    code: ({ className, children }) => {
        const match = /language-(\w+)/.exec(className || "");

        if (!match) {
            return (
                <code
                    className={cn(
                        "px-1.5 py-0.5 mx-0.5",
                        "font-mono text-[0.875em]",
                        "bg-secondary/80 dark:bg-secondary",
                        "rounded-md",
                        "text-foreground/90",
                        "border border-border/40"
                    )}
                >
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
        <blockquote
            className={cn(
                "my-6 py-4 px-5",
                "border-l-[3px] border-accent-cyan/40",
                "bg-secondary/30 dark:bg-secondary/20",
                "rounded-r-lg",
                "text-foreground/80 italic",
                "[&>p]:mb-0 [&>p]:text-[15px]"
            )}
        >
            {children}
        </blockquote>
    ),
    h1: ({ children }) => (
        <h1
            className={cn(
                "mt-8 mb-4 first:mt-0",
                "text-xl font-semibold tracking-tight",
                "text-foreground",
                "flex items-center gap-3"
            )}
        >
            <span className="w-1 h-5 bg-primary/80 rounded-full shrink-0" />
            {children}
        </h1>
    ),
    h2: ({ children }) => (
        <h2
            className={cn(
                "mt-7 mb-3 first:mt-0",
                "text-lg font-semibold tracking-tight",
                "text-foreground"
            )}
        >
            {children}
        </h2>
    ),
    h3: ({ children }) => (
        <h3
            className={cn(
                "mt-6 mb-2.5 first:mt-0",
                "text-base font-semibold",
                "text-foreground/95"
            )}
        >
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
        <th
            className={cn(
                "px-4 py-3",
                "text-left text-xs font-semibold uppercase tracking-wider",
                "text-muted-foreground"
            )}
        >
            {children}
        </th>
    ),
    td: ({ children }) => (
        <td className="px-4 py-3 text-foreground/85">{children}</td>
    ),
};
