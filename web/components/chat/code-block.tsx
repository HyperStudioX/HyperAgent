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
    swift: { name: "Swift" },
    kotlin: { name: "Kotlin" },
    ruby: { name: "Ruby" },
    php: { name: "PHP" },
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
                "border border-border/60 hover:border-border",
                "bg-secondary/30 dark:bg-secondary/20",
                "transition-colors duration-150"
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
                        <span className="w-2.5 h-2.5 rounded-full shrink-0 bg-primary/60" />
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
                        "transition-colors duration-150",
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
