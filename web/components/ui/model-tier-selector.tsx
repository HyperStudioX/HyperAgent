"use client";

import { Brain, Zap, Bolt, Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { useSettingsStore, type ModelTier } from "@/lib/stores/settings-store";

const TIER_ICONS: Record<ModelTier | "auto", React.ComponentType<{ className?: string }>> = {
  auto: Sparkles,
  max: Brain,
  pro: Zap,
  flash: Bolt,
};

interface ModelTierSelectorProps {
  className?: string;
  compact?: boolean;
}

export function ModelTierSelector({ className, compact }: ModelTierSelectorProps) {
  const t = useTranslations("settings");
  const { tier, setTier, hasHydrated } = useSettingsStore();

  const tiers: (ModelTier | "auto")[] = ["auto", "max", "pro", "flash"];

  if (!hasHydrated) return null;

  if (compact) {
    // Inline pill selector for chat interface
    return (
      <div className={cn("flex items-center gap-1", className)}>
        {tiers.map((tierOption) => {
          const Icon = TIER_ICONS[tierOption];
          return (
            <button
              key={tierOption}
              onClick={() => setTier(tierOption)}
              className={cn(
                "flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium transition-colors",
                tier === tierOption
                  ? "bg-foreground text-background"
                  : "bg-secondary text-muted-foreground hover:text-foreground"
              )}
              title={t(`tierDescription.${tierOption}`)}
            >
              <Icon className="w-3.5 h-3.5" />
              <span className="capitalize">{tierOption}</span>
            </button>
          );
        })}
      </div>
    );
  }

  // Grid selector for preferences panel
  return (
    <div className={cn("grid grid-cols-2 gap-2", className)}>
      {tiers.map((tierOption) => {
        const Icon = TIER_ICONS[tierOption];
        return (
          <button
            key={tierOption}
            onClick={() => setTier(tierOption)}
            className={cn(
              "flex items-center gap-2 px-3 py-2 rounded-lg border text-left transition-colors",
              tier === tierOption
                ? "bg-foreground text-background border-foreground"
                : "bg-background border-border hover:bg-secondary/50"
            )}
          >
            <Icon className="w-4 h-4 flex-shrink-0" />
            <div className="flex flex-col min-w-0">
              <span className="text-sm font-medium capitalize">{tierOption}</span>
              <span
                className={cn(
                  "text-xs truncate",
                  tier === tierOption ? "text-background/70" : "text-muted-foreground"
                )}
              >
                {t(`tierDescription.${tierOption}`)}
              </span>
            </div>
          </button>
        );
      })}
    </div>
  );
}
