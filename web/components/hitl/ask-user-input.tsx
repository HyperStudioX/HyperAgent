"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { useTranslations } from "next-intl";
import { Send, Clock, MessageSquare, CheckCircle2, Check, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { InterruptEvent, InterruptResponse, InterruptOption } from "@/lib/types";

interface AskUserInputProps {
    interrupt: InterruptEvent;
    onRespond: (response: InterruptResponse) => void;
    onCancel: () => void;
}

// Countdown display (inline, subtle)
function CountdownBadge({ seconds, onExpire }: { seconds: number; onExpire: () => void }) {
    const [remaining, setRemaining] = useState(seconds);

    // Reset remaining when seconds prop changes (new interrupt)
    useEffect(() => {
        setRemaining(seconds);
    }, [seconds]);

    useEffect(() => {
        if (remaining <= 0) {
            onExpire();
            return;
        }

        const timer = setInterval(() => {
            setRemaining((prev) => {
                if (prev <= 1) {
                    clearInterval(timer);
                    return 0;
                }
                return prev - 1;
            });
        }, 1000);

        return () => clearInterval(timer);
    }, [remaining, onExpire]);

    const minutes = Math.floor(remaining / 60);
    const secs = remaining % 60;
    const isLow = remaining <= 30;

    return (
        <span className={cn(
            "inline-flex items-center gap-1 text-xs tabular-nums",
            isLow ? "text-destructive" : "text-muted-foreground"
        )}>
            <Clock className="w-4 h-4" />
            {minutes}:{secs.toString().padStart(2, "0")}
        </span>
    );
}

// Decision/Choice buttons
function DecisionInput({
    options,
    onSelect,
}: {
    options: InterruptOption[];
    onSelect: (value: string) => void;
}) {
    const [selected, setSelected] = useState<string | null>(null);

    return (
        <div className="flex flex-wrap gap-2">
            {options.map((option) => (
                <button
                    key={option.value}
                    className={cn(
                        "px-3 py-1.5 text-sm rounded-lg border transition-colors",
                        "focus-visible:ring-2 focus-visible:ring-foreground/20 focus-visible:ring-offset-2 focus-visible:outline-none",
                        selected === option.value
                            ? "bg-foreground text-background border-foreground"
                            : "bg-card text-muted-foreground border-border hover:bg-secondary hover:text-foreground"
                    )}
                    onClick={() => {
                        setSelected(option.value);
                        onSelect(option.value);
                    }}
                >
                    {selected === option.value && (
                        <CheckCircle2 className="w-4 h-4 inline mr-1.5 -ml-0.5" />
                    )}
                    {option.label}
                </button>
            ))}
        </div>
    );
}

// Boolean Yes/No input
function BooleanInput({
    onSelect,
}: {
    onSelect: (value: boolean) => void;
}) {
    const t = useTranslations("hitl");

    return (
        <div className="flex gap-2">
            <button
                className={cn(
                    "flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-lg border transition-colors",
                    "focus-visible:ring-2 focus-visible:ring-foreground/20 focus-visible:ring-offset-2 focus-visible:outline-none",
                    "bg-card text-foreground border-border hover:bg-foreground hover:text-background"
                )}
                onClick={() => onSelect(true)}
            >
                <Check className="w-4 h-4" />
                {t("yes")}
            </button>
            <button
                className={cn(
                    "flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-lg border transition-colors",
                    "focus-visible:ring-2 focus-visible:ring-foreground/20 focus-visible:ring-offset-2 focus-visible:outline-none",
                    "bg-card text-muted-foreground border-border hover:bg-secondary hover:text-foreground"
                )}
                onClick={() => onSelect(false)}
            >
                <X className="w-4 h-4" />
                {t("no")}
            </button>
        </div>
    );
}

// Text input field
function TextInput({
    onSubmit,
    placeholder,
}: {
    onSubmit: (value: string) => void;
    placeholder?: string;
}) {
    const [value, setValue] = useState("");
    const inputRef = useRef<HTMLTextAreaElement>(null);

    useEffect(() => {
        // Auto-focus with slight delay for animation
        const timer = setTimeout(() => inputRef.current?.focus(), 100);
        return () => clearTimeout(timer);
    }, []);

    const handleSubmit = () => {
        if (value.trim()) {
            onSubmit(value.trim());
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
            e.preventDefault();
            handleSubmit();
        }
    };

    return (
        <div className="flex gap-2 items-end">
            <Textarea
                ref={inputRef}
                value={value}
                onChange={(e) => setValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={placeholder || "Type your response..."}
                rows={1}
                className="min-h-[38px] max-h-[120px] resize-none flex-1 text-sm"
            />
            <Button
                size="sm"
                variant="primary"
                onClick={handleSubmit}
                disabled={!value.trim()}
                className="h-[38px] px-3"
            >
                <Send className="w-4 h-4" />
            </Button>
        </div>
    );
}

export function AskUserInput({ interrupt, onRespond, onCancel }: AskUserInputProps) {
    const t = useTranslations("hitl");

    // Debug: Log when component renders with new interrupt
    console.log("[AskUserInput] Rendering with interrupt:", {
        interrupt_id: interrupt.interrupt_id,
        message: interrupt.message?.substring(0, 50),
        options: interrupt.options?.map(o => o.label),
        interrupt_type: interrupt.interrupt_type,
    });

    const handleExpire = useCallback(() => {
        onRespond({
            interrupt_id: interrupt.interrupt_id,
            action: interrupt.default_action as InterruptResponse["action"] || "skip",
        });
    }, [interrupt, onRespond]);

    const handleSelect = useCallback((value: string) => {
        onRespond({
            interrupt_id: interrupt.interrupt_id,
            action: "select",
            value,
        });
    }, [interrupt, onRespond]);

    const handleInput = useCallback((value: string) => {
        onRespond({
            interrupt_id: interrupt.interrupt_id,
            action: "input",
            value,
        });
    }, [interrupt, onRespond]);

    const handleSkip = useCallback(() => {
        onRespond({
            interrupt_id: interrupt.interrupt_id,
            action: "skip",
        });
    }, [interrupt, onRespond]);

    const handleBoolean = useCallback((value: boolean) => {
        onRespond({
            interrupt_id: interrupt.interrupt_id,
            action: value ? "approve" : "deny",
            value: value ? "yes" : "no",
        });
    }, [interrupt, onRespond]);

    const isDecision = interrupt.interrupt_type === "decision" && interrupt.options;
    const isInput = interrupt.interrupt_type === "input";
    const isConfirm = interrupt.interrupt_type === "confirm";

    return (
        <div className="bg-secondary/30 border border-border/50 rounded-xl p-4 space-y-3 animate-fade-in">
            {/* Header with question and timer */}
            <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-2 flex-1 min-w-0">
                    <MessageSquare className="w-4 h-4 text-foreground mt-0.5 flex-shrink-0" />
                    <p className="text-sm text-foreground leading-relaxed">
                        {interrupt.message}
                    </p>
                </div>
                <CountdownBadge
                    seconds={interrupt.timeout_seconds}
                    onExpire={handleExpire}
                />
            </div>

            {/* Input area */}
            <div className="pl-6">
                {isDecision && interrupt.options && (
                    <DecisionInput
                        options={interrupt.options}
                        onSelect={handleSelect}
                    />
                )}
                {isInput && (
                    <TextInput
                        onSubmit={handleInput}
                        placeholder={t("inputPlaceholder")}
                    />
                )}
                {isConfirm && (
                    <BooleanInput onSelect={handleBoolean} />
                )}
            </div>

            {/* Skip option */}
            <div className="pl-6">
                <button
                    onClick={handleSkip}
                    className="text-xs text-muted-foreground hover:text-foreground transition-colors focus-visible:ring-2 focus-visible:ring-foreground/20 focus-visible:outline-none rounded"
                >
                    {t("skip")}
                </button>
            </div>
        </div>
    );
}
