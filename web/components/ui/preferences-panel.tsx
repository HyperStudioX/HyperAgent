"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useTranslations, useLocale } from "next-intl";
import { Sun, Moon, Globe, Monitor } from "lucide-react";
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
    setIsOpen(false);
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
          "text-xs font-medium tracking-wide",
          "text-muted-foreground hover:text-foreground",
          "border border-border hover:border-foreground/20",
          "transition-colors",
          isOpen && "text-foreground border-foreground/20"
        )}
      >
        <div className="flex items-center gap-1.5">
          {mounted && <ThemeIcon className="w-3.5 h-3.5" />}
          <span>{currentLocale.shortLabel}</span>
        </div>
        <div className={cn(
          "w-1 h-1 rounded-full bg-current transition-transform",
          isOpen && "rotate-180"
        )} />
      </button>

      {/* Menu */}
      {isOpen && (
        <div
          className={cn(
            "absolute bottom-full left-0 right-0 mb-1.5 z-50",
            "bg-card border border-border rounded-lg",
            "shadow-lg",
            "overflow-hidden"
          )}
        >
          {/* Theme */}
          <div className="border-b border-border">
            <div className="px-3 py-1.5">
              <div className="text-[10px] font-medium text-muted-foreground/60 uppercase tracking-widest">
                {t("theme")}
              </div>
            </div>
            <div className="grid grid-cols-3 gap-0.5 p-1">
              <button
                onClick={() => handleThemeChange("auto")}
                className={cn(
                  "h-8 rounded flex items-center justify-center gap-1.5",
                  "text-xs font-medium transition-colors",
                  mounted && theme === "auto"
                    ? "bg-foreground text-background"
                    : "text-muted-foreground hover:text-foreground hover:bg-secondary"
                )}
              >
                <Monitor className="w-3.5 h-3.5" />
                <span>{t("auto")}</span>
              </button>
              <button
                onClick={() => handleThemeChange("light")}
                className={cn(
                  "h-8 rounded flex items-center justify-center gap-1.5",
                  "text-xs font-medium transition-colors",
                  mounted && theme === "light"
                    ? "bg-foreground text-background"
                    : "text-muted-foreground hover:text-foreground hover:bg-secondary"
                )}
              >
                <Sun className="w-3.5 h-3.5" />
                <span>{t("light")}</span>
              </button>
              <button
                onClick={() => handleThemeChange("dark")}
                className={cn(
                  "h-8 rounded flex items-center justify-center gap-1.5",
                  "text-xs font-medium transition-colors",
                  mounted && theme === "dark"
                    ? "bg-foreground text-background"
                    : "text-muted-foreground hover:text-foreground hover:bg-secondary"
                )}
              >
                <Moon className="w-3.5 h-3.5" />
                <span>{t("dark")}</span>
              </button>
            </div>
          </div>

          {/* Language */}
          <div>
            <div className="px-3 py-1.5">
              <div className="text-[10px] font-medium text-muted-foreground/60 uppercase tracking-widest">
                {t("language")}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-0.5 p-1">
              {LOCALES.map((loc) => (
                <button
                  key={loc.code}
                  onClick={() => handleLocaleChange(loc.code)}
                  className={cn(
                    "h-8 rounded flex items-center justify-center gap-1.5",
                    "text-xs font-medium transition-colors",
                    currentLocale.code === loc.code
                      ? "bg-foreground text-background"
                      : "text-muted-foreground hover:text-foreground hover:bg-secondary"
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
