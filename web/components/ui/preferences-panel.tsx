"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useTranslations, useLocale } from "next-intl";
import { Sun, Moon, Globe, Monitor, ChevronUp } from "lucide-react";
import { cn } from "@/lib/utils";

interface PreferencesPanelProps {
  theme: "light" | "dark" | "auto";
  mounted: boolean;
  onThemeChange: (theme: "light" | "dark" | "auto") => void;
  className?: string;
}

const LOCALES = [
  { code: "en", label: "English", shortLabel: "EN" },
  { code: "zh-CN", label: "简体中文", shortLabel: "中文" },
] as const;

export function PreferencesPanel({
  theme,
  mounted,
  onThemeChange,
  className,
}: PreferencesPanelProps) {
  const t = useTranslations("sidebar");
  const locale = useLocale();
  const router = useRouter();
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const handleLocaleChange = (newLocale: string) => {
    document.cookie = `locale=${newLocale};path=/;max-age=31536000`;
    setIsOpen(false);
    router.refresh();
  };

  const handleThemeChange = (newTheme: "light" | "dark" | "auto") => {
    onThemeChange(newTheme);
  };

  const currentLocale = LOCALES.find((l) => l.code === locale) || LOCALES[0];

  // Get icon for current theme
  const ThemeIcon = theme === "auto" ? Monitor : theme === "dark" ? Moon : Sun;

  // Close menu when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div ref={menuRef} className={cn("relative", className)}>
      {/* Trigger */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "w-full h-9 px-3 rounded-lg",
          "flex items-center justify-between",
          "text-sm",
          "text-muted-foreground hover:text-foreground",
          "hover:bg-secondary",
          "transition-all duration-200"
        )}
      >
        <div className="flex items-center gap-2">
          {mounted && <ThemeIcon className="w-4 h-4" />}
          <span>{t("preferences")}</span>
        </div>
        <ChevronUp className={cn(
          "w-4 h-4 transition-transform",
          isOpen ? "rotate-0" : "rotate-180"
        )} />
      </button>

      {/* Menu */}
      {isOpen && (
        <div
          className={cn(
            "absolute bottom-full left-0 right-0 mb-1 z-50",
            "bg-card border border-border rounded-xl shadow-lg",
            "overflow-hidden animate-scale-in"
          )}
        >
          {/* Theme */}
          <div className="p-2 border-b border-border">
            <div className="px-2 py-1">
              <span className="text-xs font-medium text-muted-foreground">
                {t("theme")}
              </span>
            </div>
            <div className="flex gap-1">
              {[
                { value: "auto", icon: Monitor, label: t("auto") },
                { value: "light", icon: Sun, label: t("light") },
                { value: "dark", icon: Moon, label: t("dark") },
              ].map(({ value, icon: Icon, label }) => (
                <button
                  key={value}
                  onClick={() => handleThemeChange(value as "light" | "dark" | "auto")}
                  className={cn(
                    "flex-1 h-8 rounded-lg flex items-center justify-center gap-1.5",
                    "text-xs font-medium transition-colors",
                    mounted && theme === value
                      ? "bg-secondary text-foreground"
                      : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
                  )}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Language */}
          <div className="p-2">
            <div className="px-2 py-1">
              <span className="text-xs font-medium text-muted-foreground">
                {t("language")}
              </span>
            </div>
            <div className="flex gap-1">
              {LOCALES.map((loc) => (
                <button
                  key={loc.code}
                  onClick={() => handleLocaleChange(loc.code)}
                  className={cn(
                    "flex-1 h-8 rounded-lg flex items-center justify-center gap-1.5",
                    "text-xs font-medium transition-colors",
                    currentLocale.code === loc.code
                      ? "bg-secondary text-foreground"
                      : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
                  )}
                >
                  <Globe className="w-3.5 h-3.5" />
                  <span>{loc.shortLabel}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
