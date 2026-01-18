"use client";

import React, { useState, useRef, useCallback, forwardRef, useImperativeHandle, KeyboardEvent, memo } from "react";
import { useTranslations } from "next-intl";
import { ArrowUp, Loader2, Square } from "lucide-react";
import { cn } from "@/lib/utils";

export interface ChatInputHandle {
  focus: () => void;
  clear: () => void;
  getValue: () => string;
  setValue: (value: string) => void;
}

interface ChatInputProps {
  onSubmit: (value: string) => void;
  onStop?: () => void;
  isLoading?: boolean;
  placeholder?: string;
  className?: string;
  initialValue?: string;
}

export const ChatInput = memo(
  forwardRef<ChatInputHandle, ChatInputProps>(function ChatInput(
    {
      onSubmit,
      onStop,
      isLoading = false,
      placeholder,
      className,
      initialValue = "",
    },
    ref
  ) {
    const t = useTranslations("chat");
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const [value, setValue] = useState(initialValue);

    useImperativeHandle(ref, () => ({
      focus: () => textareaRef.current?.focus(),
      clear: () => setValue(""),
      getValue: () => value,
      setValue: (newValue: string) => setValue(newValue),
    }));

    const handleSubmit = useCallback(() => {
      const trimmed = value.trim();
      if (!trimmed || isLoading) return;
      onSubmit(trimmed);
      setValue("");
    }, [value, isLoading, onSubmit]);

    const handleKeyDown = useCallback(
      (e: KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
          e.preventDefault();
          handleSubmit();
        }
      },
      [handleSubmit]
    );

    const canSubmit = value.trim() && !isLoading;

    return (
      <div className={cn("relative", className)}>
        <div className="relative flex items-end bg-card rounded-2xl border border-border focus-within:border-foreground/30 focus-within:shadow-glow-sm transition-all duration-200">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder || t("typeMessage")}
            disabled={isLoading}
            className="flex-1 min-h-[52px] max-h-[160px] px-4 py-3.5 bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none disabled:opacity-50 textarea-auto-resize"
            rows={1}
          />
          <div className="p-2">
            {isLoading && onStop ? (
              <button
                onClick={onStop}
                className="w-8 h-8 rounded-xl flex items-center justify-center transition-all bg-destructive text-destructive-foreground hover:bg-destructive/90"
                title={t("stop")}
              >
                <Square className="w-3.5 h-3.5 fill-current" />
              </button>
            ) : (
              <button
                onClick={handleSubmit}
                disabled={!canSubmit}
                className={cn(
                  "group w-8 h-8 rounded-xl flex items-center justify-center transition-all duration-150",
                  canSubmit
                    ? "bg-accent-cyan text-foreground dark:text-background hover:bg-accent-cyan/90 hover:-translate-y-0.5 active:scale-[0.98] interactive-glow border border-accent-cyan/20"
                    : "bg-secondary text-muted-foreground"
                )}
                aria-label={canSubmit ? t("send") : t("typeMessage")}
              >
                {isLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <ArrowUp className="w-4 h-4 group-hover:-translate-y-0.5 group-hover:scale-110 transition-transform" />
                )}
              </button>
            )}
          </div>
        </div>
        <p className="mt-2 text-xs text-center text-muted-foreground/60">
          {t("pressEnterToSend")}
        </p>
      </div>
    );
  })
);
