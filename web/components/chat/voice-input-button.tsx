"use client";

import React, { useCallback, useEffect } from "react";
import { Mic, Loader2, MicOff } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { useVoiceRecording } from "@/lib/hooks/use-voice-recording";

interface VoiceInputButtonProps {
  onTranscription: (text: string) => void;
  disabled?: boolean;
  className?: string;
}

export function VoiceInputButton({
  onTranscription,
  disabled = false,
  className,
}: VoiceInputButtonProps) {
  const t = useTranslations("chat.voice");

  const {
    state,
    isSupported,
    error,
    startRecording,
    stopRecording,
    cancelRecording,
  } = useVoiceRecording({
    onTranscriptionComplete: onTranscription,
    onError: (err) => console.error("[VoiceInput]", err),
  });

  const handleClick = useCallback(async () => {
    if (state === "idle") {
      await startRecording();
    } else if (state === "recording") {
      await stopRecording();
    }
    // Do nothing if transcribing - let it complete
  }, [state, startRecording, stopRecording]);

  // Handle escape key to cancel recording
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && state === "recording") {
        cancelRecording();
      }
    };

    if (state === "recording") {
      window.addEventListener("keydown", handleKeyDown);
      return () => window.removeEventListener("keydown", handleKeyDown);
    }
  }, [state, cancelRecording]);

  // Don't render if not supported
  if (!isSupported) {
    return null;
  }

  const getIcon = () => {
    switch (state) {
      case "recording":
        return <Mic className="w-5 h-5" />;
      case "transcribing":
        return <Loader2 className="w-5 h-5 animate-spin" />;
      case "error":
        return <MicOff className="w-5 h-5" />;
      default:
        return <Mic className="w-5 h-5" />;
    }
  };

  const getTitle = () => {
    switch (state) {
      case "recording":
        return t("stopRecording");
      case "transcribing":
        return t("transcribing");
      case "error":
        return error || t("error");
      default:
        return t("startRecording");
    }
  };

  const isRecording = state === "recording";
  const isTranscribing = state === "transcribing";
  const isDisabled = disabled || isTranscribing;

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={isDisabled}
      className={cn(
        "flex items-center justify-center",
        "w-9 h-9 rounded-lg",
        "transition-colors",
        isRecording
          ? "bg-destructive/10 text-destructive animate-pulse-recording"
          : "text-muted-foreground hover:text-foreground hover:bg-secondary/80",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        className
      )}
      title={getTitle()}
      aria-label={getTitle()}
      aria-pressed={isRecording}
    >
      {getIcon()}
    </button>
  );
}
