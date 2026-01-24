"use client";

import React, { useState, useRef, useCallback, forwardRef, useImperativeHandle, KeyboardEvent, memo } from "react";
import { useTranslations } from "next-intl";
import { ArrowUp, Loader2, Square } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

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
        <div className="relative flex items-end bg-card rounded-xl border border-border focus-within:border-foreground/30 transition-colors duration-200">
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
              <Button
                onClick={onStop}
                variant="secondary"
                size="icon"
                title={t("stop")}
              >
                <Square className="w-3.5 h-3.5 fill-current" />
              </Button>
            ) : (
              <Button
                onClick={handleSubmit}
                disabled={!canSubmit}
                variant={canSubmit ? "primary" : "default"}
                size="icon"
                aria-label={canSubmit ? t("send") : t("typeMessage")}
              >
                {isLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <ArrowUp className="w-4 h-4" />
                )}
              </Button>
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
