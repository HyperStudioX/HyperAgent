import React from "react";
import {
    Send,
    Square,
    Check,
    Zap,
    Layers,
    ChevronDown,
    Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { FileUploadButton } from "@/components/chat/file-upload-button";
import { AttachmentPreview } from "@/components/chat/attachment-preview";
import { Button } from "@/components/ui/button";
import { CostIndicator } from "@/components/ui/cost-indicator";
import { SkillSelector } from "@/components/chat/skill-selector";
import type { FileAttachment, AgentEvent } from "@/lib/types";
import { ChatHomeView } from "./chat-home-view";

type ModelTier = "max" | "pro" | "lite";

export interface ChatInputBarProps {
    hasMessages: boolean;
    input: string;
    onInputChange: (value: string) => void;
    onSubmit: () => void;
    onStop: () => void;
    isProcessing: boolean;
    isUploading: boolean;
    inputRef: React.RefObject<HTMLTextAreaElement>;
    placeholder: string;
    attachments: FileAttachment[];
    onRemoveAttachment: (id: string) => void;
    onFilesSelected: (files: File[]) => void;
    onSourceSelect: (sourceId: string) => void;
    tier: ModelTier;
    onTierChange: (tier: ModelTier) => void;
    showModelMenu: boolean;
    onToggleModelMenu: () => void;
    modelMenuRef: React.RefObject<HTMLDivElement>;
    selectedSkill: string | null;
    onSkillChange: (skill: string | null) => void;
    allUsageEvents: AgentEvent[];
    welcomeTitle: string;
    welcomeSubtitle: string;
    tSettings: (key: string) => string;
    tChat: (key: string, values?: Record<string, string | number>) => string;
}

export function ChatInputBar({
    hasMessages,
    input,
    onInputChange,
    onSubmit,
    onStop,
    isProcessing,
    isUploading,
    inputRef,
    placeholder,
    attachments,
    onRemoveAttachment,
    onFilesSelected,
    onSourceSelect,
    tier,
    onTierChange,
    showModelMenu,
    onToggleModelMenu,
    modelMenuRef,
    selectedSkill,
    onSkillChange,
    allUsageEvents,
    welcomeTitle,
    welcomeSubtitle,
    tSettings,
    tChat,
}: ChatInputBarProps) {
    return (
        <div
            className={cn(
                "flex flex-col",
                hasMessages ? "bg-background/80 pb-2" : "flex-1 items-center justify-center"
            )}
        >
            <div
                className={cn(
                    "w-full",
                    hasMessages ? "max-w-4xl mx-auto px-4 md:px-6 py-3 md:py-4" : "max-w-2xl px-6 md:px-8"
                )}
            >
                {!hasMessages && (
                    <ChatHomeView
                        welcomeTitle={welcomeTitle}
                        welcomeSubtitle={welcomeSubtitle}
                    />
                )}

                <div className="relative">
                    <div className={cn(
                        "relative flex flex-col bg-card rounded-2xl border transition-colors",
                        hasMessages
                            ? "border-border focus-within:border-foreground/15"
                            : "border-border/50 shadow-sm focus-within:shadow-md focus-within:border-foreground/20"
                    )}>
                        <AttachmentPreview
                            attachments={attachments}
                            onRemove={onRemoveAttachment}
                        />

                        <div className="flex items-end">
                            <textarea
                                ref={inputRef}
                                value={input}
                                onChange={(e) => onInputChange(e.target.value)}
                                placeholder={placeholder}
                                className={cn(
                                    "flex-1 bg-transparent text-foreground placeholder:text-muted-foreground/50 focus:outline-none leading-relaxed textarea-auto-resize resize-none",
                                    hasMessages
                                        ? "min-h-[48px] max-h-[140px] px-4 py-3 text-sm"
                                        : "min-h-[72px] md:min-h-[88px] max-h-[180px] px-5 py-4 md:py-5 text-base tracking-[-0.01em]"
                                )}
                                rows={hasMessages ? 2 : 3}
                                onKeyDown={(e) => {
                                    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                                        e.preventDefault();
                                        onSubmit();
                                    }
                                }}
                            />
                        </div>

                        <div className="flex items-center justify-between px-3 md:px-4 pb-3 pt-1.5 border-t border-border/30">
                            <div className="flex items-center gap-2">
                                <FileUploadButton
                                    onFilesSelected={onFilesSelected}
                                    onSourceSelect={onSourceSelect}
                                    disabled={isProcessing || isUploading}
                                />

                                <div ref={modelMenuRef} className="relative">
                                    <button
                                        onClick={onToggleModelMenu}
                                        className={cn(
                                            "flex items-center gap-1.5 px-2.5 py-1 rounded-full",
                                            "text-xs font-semibold tracking-wide transition-all duration-150",
                                            "cursor-pointer active:scale-[0.97]",
                                            {
                                                max: "bg-warning/10 text-warning hover:bg-warning/15",
                                                pro: "bg-primary/10 text-primary hover:bg-primary/15",
                                                lite: "bg-success/10 text-success hover:bg-success/15",
                                            }[tier]
                                        )}
                                    >
                                        <Layers className="w-3 h-3" />
                                        <span>{tier.charAt(0).toUpperCase() + tier.slice(1)}</span>
                                        <ChevronDown className={cn("w-3 h-3 opacity-60 transition-transform duration-200", showModelMenu && "rotate-180")} />
                                    </button>

                                    {showModelMenu && (
                                        <div className={cn(
                                            "absolute bottom-full left-0 mb-2 z-50",
                                            "w-[340px] rounded-xl overflow-hidden",
                                            "bg-popover border border-border/80 shadow-xl shadow-black/8 dark:shadow-black/25",
                                            "animate-in fade-in-0 slide-in-from-bottom-2 duration-150"
                                        )}>
                                            <div className="p-2 grid grid-cols-2 gap-1">
                                                {([
                                                    { key: "max" as const, icon: Sparkles, bg: "bg-warning/10", text: "text-warning", activeBg: "bg-warning/12", activeText: "text-warning" },
                                                    { key: "pro" as const, icon: Layers, bg: "bg-primary/10", text: "text-primary", activeBg: "bg-primary/12", activeText: "text-primary" },
                                                    { key: "lite" as const, icon: Zap, bg: "bg-success/10", text: "text-success", activeBg: "bg-success/12", activeText: "text-success" },
                                                ]).map(({ key: tierOption, icon: TierIcon, bg, text, activeBg, activeText }) => {
                                                    const isSelected = tier === tierOption;
                                                    return (
                                                        <button
                                                            key={tierOption}
                                                            onClick={() => {
                                                                onTierChange(tierOption);
                                                            }}
                                                            className={cn(
                                                                "flex items-center gap-2.5 px-2.5 py-2.5 rounded-lg text-left transition-colors",
                                                                "cursor-pointer hover:bg-accent/60",
                                                                isSelected && "bg-primary/[0.06] dark:bg-primary/[0.08] ring-1 ring-primary/15"
                                                            )}
                                                        >
                                                            <div className={cn(
                                                                "flex items-center justify-center w-7 h-7 rounded-md shrink-0",
                                                                isSelected ? cn(activeBg, activeText) : cn(bg, text)
                                                            )}>
                                                                <TierIcon className="w-3.5 h-3.5" />
                                                            </div>
                                                            <div className="flex-1 min-w-0">
                                                                <span className="text-sm font-medium text-foreground block truncate">
                                                                    {tierOption.charAt(0).toUpperCase() + tierOption.slice(1)}
                                                                </span>
                                                                <span className="text-xs text-muted-foreground block truncate leading-tight mt-0.5">
                                                                    {tSettings(`tierDescription.${tierOption}`)}
                                                                </span>
                                                            </div>
                                                            {isSelected && (
                                                                <Check className="w-3.5 h-3.5 text-primary shrink-0" />
                                                            )}
                                                        </button>
                                                    );
                                                })}
                                            </div>
                                        </div>
                                    )}
                                </div>

                                <span className="w-px h-4 bg-border/50" />

                                <SkillSelector
                                    value={selectedSkill}
                                    onChange={onSkillChange}
                                    disabled={isProcessing}
                                />

                                <span className="w-px h-4 bg-border/50 hidden md:block" />

                                {allUsageEvents.length > 0 && hasMessages ? (
                                    <CostIndicator events={allUsageEvents} />
                                ) : (
                                    <p className="text-xs text-muted-foreground/50 tracking-wide hidden md:block">
                                        {attachments.length > 0
                                            ? tChat("filesAttached", { count: attachments.length })
                                            : tChat("pressEnterToSend")}
                                    </p>
                                )}
                            </div>
                            <Button
                                onClick={isProcessing ? onStop : onSubmit}
                                disabled={isUploading || (!isProcessing && !input.trim())}
                                variant={isProcessing ? "destructive" : (input.trim() && !isUploading ? "primary" : "ghost")}
                                size="icon"
                                className="rounded-full h-8 w-8"
                            >
                                {isProcessing ? (
                                    <Square className="w-3.5 h-3.5 fill-current" />
                                ) : (
                                    <Send className="w-3.5 h-3.5" />
                                )}
                            </Button>
                        </div>
                    </div>
                </div>

            </div>
        </div>
    );
}
