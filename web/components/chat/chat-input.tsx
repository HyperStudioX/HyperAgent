"use client";

import React, { useRef, useEffect, KeyboardEvent } from "react";
import { useTranslations } from "next-intl";
import { ArrowUp, Loader2, Square } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onStop?: () => void;
  isLoading?: boolean;
  placeholder?: string;
  className?: string;
}

export function ChatInput({
  value,
  onChange,
  onSubmit,
  onStop,
  isLoading = false,
  placeholder,
  className,
}: ChatInputProps) {
  const t = useTranslations("chat");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        160
      )}px`;
    }
  }, [value]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      if (value.trim() && !isLoading) {
        onSubmit();
      }
    }
  };

  const canSubmit = value.trim() && !isLoading;

  return (
    <div className={cn("relative", className)}>
      <div className="relative flex items-end bg-secondary/50 rounded-xl border border-border focus-within:border-primary/50 transition-colors">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder || t("typeMessage")}
          disabled={isLoading}
          className="flex-1 min-h-[52px] max-h-[160px] px-4 py-3.5 bg-transparent text-sm text-foreground placeholder:text-muted-foreground resize-none focus:outline-none disabled:opacity-50"
          rows={1}
        />
        <div className="p-2">
          {isLoading && onStop ? (
            <button
              onClick={onStop}
              className="w-8 h-8 rounded-lg flex items-center justify-center transition-all bg-destructive text-destructive-foreground hover:bg-destructive/90"
              title={t("stop")}
            >
              <Square className="w-3.5 h-3.5 fill-current" />
            </button>
          ) : (
            <button
              onClick={onSubmit}
              disabled={!canSubmit}
              className={cn(
                "w-8 h-8 rounded-lg flex items-center justify-center transition-all",
                canSubmit
                  ? "bg-primary text-primary-foreground hover:bg-primary/90"
                  : "bg-secondary text-muted-foreground"
              )}
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <ArrowUp className="w-4 h-4" />
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
}
