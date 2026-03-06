"use client";

import React, { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark, oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { useTheme } from "@/lib/hooks/use-theme";

export function TextFilePreview({ url }: { url: string }) {
    const t = useTranslations("preview");
    const [content, setContent] = useState<string | null>(null);
    const [error, setError] = useState(false);

    useEffect(() => {
        fetch(url, { credentials: 'include' })
            .then(res => res.text())
            .then(text => setContent(text.slice(0, 50000)))
            .catch(() => setError(true));
    }, [url]);

    if (error) return <>{t("failedToLoad")}</>;
    if (content === null) return <>{t("loadingContent")}</>;
    return <>{content}</>;
}

export function CodeFilePreview({ url, language, filename }: { url: string; language: string; filename: string }) {
    const t = useTranslations("preview");
    const [content, setContent] = useState<string | null>(null);
    const { resolvedTheme } = useTheme();

    useEffect(() => {
        fetch(url, { credentials: 'include' })
            .then(res => res.text())
            .then(text => setContent(text.slice(0, 50000)))
            .catch(() => setContent("// " + t("failedToLoad")));
    }, [url, t]);

    const isDark = resolvedTheme === "dark";

    if (content === null) {
        return <div className="p-6 text-sm text-muted-foreground">{t("loading")}</div>;
    }

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between px-1">
                <span className="text-xs font-mono text-muted-foreground">{filename}</span>
                <span className="text-xs uppercase tracking-wider font-bold text-primary/70 bg-primary/10 px-2 py-0.5 rounded">
                    {language}
                </span>
            </div>
            <div className="rounded-xl border border-border/50 overflow-hidden">
                <SyntaxHighlighter
                    language={language}
                    style={isDark ? oneDark : oneLight}
                    customStyle={{
                        margin: 0,
                        padding: '1.5rem',
                        background: 'transparent',
                        fontSize: '13px',
                        lineHeight: '1.6',
                    }}
                    showLineNumbers
                    lineNumberStyle={{ minWidth: '3em', paddingRight: '1em', opacity: 0.5, textAlign: 'right' }}
                >
                    {content}
                </SyntaxHighlighter>
            </div>
        </div>
    );
}

export function MarkdownPreview({ url }: { url: string }) {
    const t = useTranslations("preview");
    const [content, setContent] = useState<string | null>(null);

    useEffect(() => {
        fetch(url, { credentials: 'include' })
            .then(res => res.text())
            .then(text => setContent(text.slice(0, 100000)))
            .catch(() => setContent("# " + t("failedToLoad")));
    }, [url, t]);

    if (content === null) {
        return <div className="p-6 text-sm text-muted-foreground">{t("loading")}</div>;
    }

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

export function ImagePreview({ url, filename }: { url: string; filename: string }) {
    const t = useTranslations("preview");
    const [blobUrl, setBlobUrl] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let objectUrl: string | null = null;

        fetch(url, { credentials: 'include' })
            .then(res => {
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                return res.blob();
            })
            .then(blob => {
                objectUrl = URL.createObjectURL(blob);
                setBlobUrl(objectUrl);
            })
            .catch(err => {
                setError(err.message);
            });

        return () => {
            if (objectUrl) URL.revokeObjectURL(objectUrl);
        };
    }, [url]);

    if (error) return <p className="text-destructive p-4">{t("failedToLoadImage", { error })}</p>;
    if (!blobUrl) return <p className="text-muted-foreground animate-pulse p-4">{t("loadingImage")}</p>;

    return (
        <img
            src={blobUrl}
            alt={filename}
            className="max-w-full h-auto object-contain"
        />
    );
}

export function PDFPreview({ url, filename }: { url: string; filename: string }) {
    const t = useTranslations("preview");
    const [blobUrl, setBlobUrl] = useState<string | null>(null);

    useEffect(() => {
        let objectUrl: string | null = null;

        fetch(url, { credentials: 'include' })
            .then(res => res.blob())
            .then(blob => {
                objectUrl = URL.createObjectURL(blob);
                setBlobUrl(objectUrl);
            })
            .catch(console.error);

        return () => {
            if (objectUrl) URL.revokeObjectURL(objectUrl);
        };
    }, [url]);

    if (!blobUrl) return <div className="h-[400px] flex items-center justify-center text-muted-foreground">{t("loadingPdf")}</div>;

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
