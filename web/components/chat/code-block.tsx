"use client";

import React, { useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import {
    oneDark,
    oneLight,
} from "react-syntax-highlighter/dist/esm/styles/prism";
import { Copy, Check } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { useTheme } from "@/lib/hooks/use-theme";

// Pre-computed code themes with custom overrides
const darkCodeTheme: Record<string, React.CSSProperties> = {
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
        fontFamily:
            'ui-monospace, "SF Mono", SFMono-Regular, Menlo, Monaco, Consolas, monospace',
    },
};

const lightCodeTheme: Record<string, React.CSSProperties> = {
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
        fontFamily:
            'ui-monospace, "SF Mono", SFMono-Regular, Menlo, Monaco, Consolas, monospace',
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

interface CodeBlockProps {
    language: string;
    children: string;
}

export function CodeBlock({ language, children }: CodeBlockProps): JSX.Element {
    const [copied, setCopied] = useState(false);
    const { resolvedTheme } = useTheme();
    const t = useTranslations("chat");

    const isDark = resolvedTheme === "dark";
    const langConfig = LANGUAGE_CONFIG[language.toLowerCase()] || {
        name: language,
        color: "hsl(var(--muted-foreground))",
    };

    async function handleCopy(): Promise<void> {
        await navigator.clipboard.writeText(children);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    }

    const currentStyle = isDark ? darkCodeTheme : lightCodeTheme;
    const lineCount = children.split("\n").length;

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
                        {lineCount} {lineCount === 1 ? "line" : "lines"}
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
                            <span className="opacity-0 group-hover/code:opacity-100 transition-opacity">
                                {t("copy")}
                            </span>
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
                                fontFamily:
                                    'ui-monospace, "SF Mono", SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                            },
                        }}
                    >
                        {children}
                    </SyntaxHighlighter>
                </div>
            </div>
        </div>
    );
}
