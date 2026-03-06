"use client";

import { useEffect } from "react";
import { useTranslations } from "next-intl";
import { Cpu, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { useSettingsStore } from "@/lib/stores/settings-store";

const TIERS = ["max", "pro", "lite"] as const;

export function ModelSection() {
  const t = useTranslations("settings");
  const {
    provider,
    setProvider,
    tier,
    setTier,
    availableProviders,
    providersLoaded,
    loadProviders,
  } = useSettingsStore();

  useEffect(() => {
    if (!providersLoaded) {
      loadProviders();
    }
  }, [providersLoaded, loadProviders]);

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-base font-semibold text-foreground">
          {t("model.title")}
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          {t("model.description")}
        </p>
      </div>

      {/* Provider */}
      {availableProviders.length > 1 && (
        <div className="space-y-3">
          <label className="text-sm font-medium text-foreground">
            {t("model.provider")}
          </label>
          <div className="flex flex-wrap gap-2">
            {availableProviders.map((p) => (
              <button
                key={p.id}
                onClick={() => setProvider(p.id)}
                className={cn(
                  "flex-1 min-w-0 h-10 px-3 rounded-lg flex items-center justify-center gap-2",
                  "text-sm font-medium transition-colors",
                  "cursor-pointer",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
                  provider === p.id
                    ? "bg-primary text-primary-foreground"
                    : "bg-secondary text-muted-foreground hover:text-foreground"
                )}
              >
                <Cpu className="w-4 h-4 shrink-0" />
                <span className="truncate">{p.name}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Quality Tier */}
      <div className="space-y-3">
        <label className="text-sm font-medium text-foreground">
          {t("model.tier")}
        </label>
        <div className="space-y-2">
          {TIERS.map((t_tier) => (
            <button
              key={t_tier}
              onClick={() => setTier(t_tier)}
              className={cn(
                "w-full h-auto px-4 py-3 rounded-lg flex items-start gap-3 text-left",
                "transition-colors",
                "cursor-pointer",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
                tier === t_tier
                  ? "bg-primary text-primary-foreground"
                  : "bg-secondary text-muted-foreground hover:text-foreground"
              )}
            >
              <Sparkles className="w-4 h-4 shrink-0 mt-0.5" />
              <div className="min-w-0">
                <div className="text-sm font-medium">
                  {t_tier.charAt(0).toUpperCase() + t_tier.slice(1)}
                </div>
                <div
                  className={cn(
                    "text-xs mt-0.5",
                    tier === t_tier
                      ? "text-primary-foreground/70"
                      : "text-muted-foreground"
                  )}
                >
                  {t(`model.tier${t_tier.charAt(0).toUpperCase() + t_tier.slice(1)}` as
                    "model.tierMax" | "model.tierPro" | "model.tierLite")}
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
