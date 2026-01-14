"use client";

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import { useTranslations } from "next-intl";
import Image from "next/image";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark, oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import { Copy, Check, Terminal, RotateCcw } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTheme } from "@/lib/hooks/use-theme";
import type { Message } from "@/lib/types";

interface MessageBubbleProps {
  message: Message;
  onRegenerate?: () => void;
}

export function MessageBubble({ message, onRegenerate }: MessageBubbleProps) {
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
              "bg-foreground text-background",
              "rounded-2xl rounded-br-md",
              "shadow-sm"
            )}
          >
            <p className="text-[15px] leading-[1.65] tracking-[-0.01em] whitespace-pre-wrap font-medium">
              {message.content}
            </p>
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
              components={{
                p: ({ children }) => (
                  <p className="mb-4 last:mb-0 text-[15px] leading-[1.75] tracking-[-0.01em] text-foreground/90">
                    {children}
                  </p>
                ),
                ul: ({ children }) => (
                  <ul className="my-4 ml-1 space-y-2 list-none">
                    {React.Children.map(children, (child) =>
                      React.isValidElement(child) ? (
                        <li className="relative pl-5 text-[15px] leading-[1.7] text-foreground/90 before:absolute before:left-0 before:top-[0.6em] before:h-1.5 before:w-1.5 before:rounded-full before:bg-primary/60">
                          {child.props.children}
                        </li>
                      ) : null
                    )}
                  </ul>
                ),
                ol: ({ children }) => (
                  <ol className="my-4 ml-1 space-y-2 list-none counter-reset-[list-counter]">
                    {React.Children.map(children, (child, index) =>
                      React.isValidElement(child) ? (
                        <li className="relative pl-7 text-[15px] leading-[1.7] text-foreground/90">
                          <span className="absolute left-0 top-0 font-mono text-xs font-semibold text-primary/70 tabular-nums">
                            {String(index + 1).padStart(2, "0")}.
                          </span>
                          {child.props.children}
                        </li>
                      ) : null
                    )}
                  </ol>
                ),
                li: ({ children }) => (
                  <li className="leading-[1.7]">{children}</li>
                ),
                a: ({ href, children }) => (
                  <a
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={cn(
                      "text-primary font-medium",
                      "underline decoration-primary/30 underline-offset-[3px] decoration-[1.5px]",
                      "hover:decoration-primary/60 transition-colors duration-200"
                    )}
                  >
                    {children}
                  </a>
                ),
                code: ({ node, className, children, ...props }) => {
                  const match = /language-(\w+)/.exec(className || "");
                  const isInline = !match;

                  if (isInline) {
                    return (
                      <code
                        className={cn(
                          "px-1.5 py-0.5 mx-0.5",
                          "text-[13px] font-mono font-medium",
                          "bg-secondary/80 text-foreground/90",
                          "rounded-md",
                          "ring-1 ring-border/50"
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
                      "my-5 py-3 pl-5 pr-4",
                      "border-l-[3px] border-primary/40",
                      "bg-gradient-to-r from-muted/50 to-transparent",
                      "rounded-r-lg",
                      "[&>p]:text-muted-foreground [&>p]:italic [&>p]:text-[15px]"
                    )}
                  >
                    {children}
                  </blockquote>
                ),
                h1: ({ children }) => (
                  <h1 className="mt-8 mb-4 first:mt-0 text-xl font-semibold tracking-tight text-foreground">
                    {children}
                  </h1>
                ),
                h2: ({ children }) => (
                  <h2 className="mt-7 mb-3 first:mt-0 text-lg font-semibold tracking-tight text-foreground">
                    {children}
                  </h2>
                ),
                h3: ({ children }) => (
                  <h3 className="mt-6 mb-2.5 first:mt-0 text-base font-semibold tracking-tight text-foreground">
                    {children}
                  </h3>
                ),
                hr: () => (
                  <hr className="my-6 border-none h-px bg-gradient-to-r from-transparent via-border to-transparent" />
                ),
                strong: ({ children }) => (
                  <strong className="font-semibold text-foreground">
                    {children}
                  </strong>
                ),
                em: ({ children }) => (
                  <em className="italic text-foreground/80">{children}</em>
                ),
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>

          {/* Action buttons for assistant message */}
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
            "text-[11px] font-mono font-medium uppercase tracking-wider",
            isDark ? "text-white/50" : "text-black/50"
          )}>
            {language}
          </span>
        </div>

        <button
          onClick={handleCopy}
          className={cn(
            "flex items-center gap-1.5",
            "px-2.5 py-1.5 -my-1",
            "text-[11px] font-medium tracking-wide uppercase",
            "rounded-md",
            "transition-all duration-200",
            copied
              ? "text-emerald-600 bg-emerald-500/10"
              : isDark
                ? "text-white/40 hover:text-white/70 hover:bg-white/[0.06]"
                : "text-black/40 hover:text-black/70 hover:bg-black/[0.06]"
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
