"use client";

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useTranslations } from "next-intl";
import Image from "next/image";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark, oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import { Copy, Check, Terminal, RotateCcw, FileText, ImageIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTheme } from "@/lib/hooks/use-theme";
import type { Message, FileAttachment } from "@/lib/types";

interface MessageBubbleProps {
  message: Message;
  onRegenerate?: () => void;
  isStreaming?: boolean;
}

function MessageAttachments({ attachments }: { attachments: FileAttachment[] }) {
  if (!attachments || attachments.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2 mt-2">
      {attachments.map((attachment) => {
        const isImage = attachment.contentType.startsWith("image/");

        return (
          <div
            key={attachment.id}
            className="flex items-center gap-2 px-2 py-1.5 rounded-md bg-secondary/50 text-sm"
          >
            {isImage ? (
              <ImageIcon className="w-4 h-4 text-muted-foreground" />
            ) : (
              <FileText className="w-4 h-4 text-muted-foreground" />
            )}
            <span className="max-w-[150px] truncate">{attachment.filename}</span>
          </div>
        );
      })}
    </div>
  );
}

export function MessageBubble({ message, onRegenerate, isStreaming = false }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);
  const t = useTranslations("chat");

  const handleCopyMessage = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className={cn(
        "group py-5 transition-all duration-300",
        isUser ? "flex justify-end" : "flex justify-start"
      )}
    >
      {isUser ? (
        <div className="relative max-w-[95%] md:max-w-[80%] animate-in slide-in-from-right-2 fade-in duration-300">
          <div
            className={cn(
              "relative px-5 py-3.5",
              "bg-card text-foreground",
              "rounded-2xl rounded-br-md",
              "border border-border",
              "shadow-sm"
            )}
          >
            <p className="text-base leading-relaxed whitespace-pre-wrap">
              {message.content}
            </p>
            {message.attachments && message.attachments.length > 0 && (
              <MessageAttachments attachments={message.attachments} />
            )}
          </div>
        </div>
      ) : (
        <div className="max-w-full animate-in slide-in-from-left-2 fade-in duration-300">
          {/* Assistant header with icon and name */}
          <div className="flex items-center gap-2 mb-4">
            <Image
              src="/images/logo-dark.svg"
              alt="HyperAgent"
              width={24}
              height={24}
              className="dark:hidden rounded-md"
            />
            <Image
              src="/images/logo-light.svg"
              alt="HyperAgent"
              width={24}
              height={24}
              className="hidden dark:block rounded-md"
            />
            <span className="text-base font-semibold text-foreground">HyperAgent</span>
          </div>
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
                a: ({ href, children }) => (
                  <a
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary underline underline-offset-2 hover:text-primary/80 transition-colors"
                  >
                    {children}
                  </a>
                ),
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
              {message.content}
            </ReactMarkdown>
          </div>

          {/* Action buttons for assistant message - only show when not streaming */}
          {!isStreaming && (
            <div className="mt-3 flex items-center gap-1">
              <button
                onClick={handleCopyMessage}
                className={cn(
                  "flex items-center gap-1.5",
                  "px-2.5 py-1.5",
                  "text-xs font-medium",
                  "rounded-lg",
                  "transition-all duration-200",
                  copied
                    ? "text-emerald-600 dark:text-emerald-400 bg-emerald-500/10"
                    : "text-muted-foreground hover:text-foreground hover:bg-secondary/80"
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
                    "rounded-lg",
                    "transition-all duration-200",
                    "text-muted-foreground hover:text-foreground hover:bg-secondary/80"
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
    </div>
  );
}

interface CodeBlockProps {
  language: string;
  children: string;
}

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

  return (
    <div
      className={cn(
        "my-5 rounded-xl overflow-hidden",
        "ring-1 shadow-[0_4px_24px_-4px] transition-all duration-300",
        isDark
          ? "bg-[#282c34] ring-white/[0.08] shadow-black/20"
          : "bg-[#fafafa] ring-black/[0.08] shadow-black/5",
        isHovered && (isDark
          ? "shadow-[0_8px_32px_-4px] shadow-black/30 ring-white/[0.12]"
          : "shadow-[0_8px_32px_-4px] shadow-black/10 ring-black/[0.12]")
      )}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Header */}
      <div
        className={cn(
          "flex items-center justify-between",
          "px-3 md:px-4 py-2 md:py-2.5",
          "border-b",
          isDark
            ? "bg-white/[0.03] border-white/[0.06]"
            : "bg-black/[0.02] border-black/[0.06]"
        )}
      >
        <div className="flex items-center gap-2">
          <div className={cn(
            "w-5 h-5 rounded flex items-center justify-center",
            isDark ? "bg-white/5" : "bg-black/5"
          )}>
            <Terminal className={cn(
              "w-3 h-3",
              isDark ? "text-white/40" : "text-black/40"
            )} />
          </div>
          <span className={cn(
            "text-xs font-mono",
            isDark ? "text-white/50" : "text-black/50"
          )}>
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
              ? "text-emerald-600 bg-emerald-500/10"
              : isDark
                ? "text-white/40 hover:text-white/70 hover:bg-white/5"
                : "text-black/40 hover:text-black/70 hover:bg-black/5"
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
          style={isDark ? darkCodeTheme : lightCodeTheme}
          customStyle={{ background: "transparent", margin: 0, padding: 0 }}
        >
          {children}
        </SyntaxHighlighter>

        {/* Subtle gradient fade at bottom */}
        <div
          className={cn(
            "absolute bottom-0 left-0 right-0 h-6",
            "pointer-events-none opacity-0",
            isDark
              ? "bg-gradient-to-t from-[#282c34] to-transparent"
              : "bg-gradient-to-t from-[#fafafa] to-transparent",
            children.split("\n").length > 10 && "opacity-100"
          )}
        />
      </div>
    </div>
  );
}
