"use client";

import { useTranslations } from "next-intl";

interface TypingIndicatorProps {
    message?: string;
}

/**
 * Thinking indicator - clean pill with pulsing dot
 */
export function TypingIndicator({ message }: TypingIndicatorProps): JSX.Element {
    const t = useTranslations("chat");
    const displayMessage = message || t("agent.thinking");

    return (
        <div className="inline-flex items-center gap-2.5 px-3.5 py-2 mb-3 rounded-full bg-muted/60 border border-border/40">
            <span className="w-2 h-2 rounded-full bg-primary/80 animate-pulse" />
            <span className="text-[13px] font-medium text-muted-foreground">
                {displayMessage}
            </span>
        </div>
    );
}
