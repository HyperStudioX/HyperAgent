"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Plug, Check, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { MCPPreset } from "@/lib/types/mcp";

interface PresetCardProps {
  preset: MCPPreset;
  isConnected: boolean;
  connectedToolCount?: number;
  onEnable: (name: string) => Promise<void>;
  index?: number;
}

export function PresetCard({
  preset,
  isConnected,
  connectedToolCount,
  onEnable,
  index = 0,
}: PresetCardProps) {
  const t = useTranslations("integrations");
  const [enabling, setEnabling] = useState(false);

  async function handleEnable() {
    setEnabling(true);
    try {
      await onEnable(preset.name);
    } finally {
      setEnabling(false);
    }
  }

  return (
    <div
      className={cn(
        "group relative border rounded-xl p-4",
        "transition-all duration-200",
        isConnected
          ? "border-success/30 bg-success/5"
          : "border-border/50 hover:border-border hover:shadow-sm",
        "animate-fade-in"
      )}
      style={{ animationDelay: `${index * 40}ms`, animationFillMode: "backwards" }}
    >
      <div className="flex items-start gap-3">
        <div
          className={cn(
            "shrink-0 p-2 rounded-lg",
            isConnected ? "bg-success/10" : "bg-secondary"
          )}
        >
          <Plug
            className={cn(
              "w-4 h-4",
              isConnected ? "text-success" : "text-muted-foreground"
            )}
          />
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="font-semibold text-sm text-foreground truncate">
            {preset.name}
          </h4>
          <p className="text-xs text-muted-foreground mt-1 line-clamp-2 leading-relaxed">
            {preset.description}
          </p>
        </div>
      </div>

      <div className="flex items-center justify-between mt-3 pt-3 border-t border-border/30">
        <span className="text-xs text-muted-foreground uppercase tracking-wider font-medium">
          {preset.transport}
        </span>

        {isConnected ? (
          <div className="flex items-center gap-1.5 text-xs text-success">
            <Check className="w-3.5 h-3.5" />
            <span className="font-medium">{t("enabled")}</span>
            {connectedToolCount !== undefined && (
              <span className="text-muted-foreground ml-1">
                ({t("tools", { count: connectedToolCount })})
              </span>
            )}
          </div>
        ) : (
          <Button
            size="sm"
            variant="ghost"
            className="h-7 px-2.5 text-xs gap-1 cursor-pointer"
            onClick={handleEnable}
            disabled={enabling}
          >
            {enabling ? (
              <>
                <Loader2 className="w-3 h-3 animate-spin" />
                {t("enabling")}
              </>
            ) : (
              t("enable")
            )}
          </Button>
        )}
      </div>
    </div>
  );
}
