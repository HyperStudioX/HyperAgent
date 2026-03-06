"use client";

import { useRouter } from "next/navigation";
import { useTranslations, useLocale } from "next-intl";
import { Sun, Moon, Monitor, Globe } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTheme } from "@/lib/hooks/use-theme";

const LOCALES = [
  { code: "en", label: "English", shortLabel: "EN" },
  { code: "zh-CN", label: "简体中文", shortLabel: "中文" },
] as const;

export function GeneralSection() {
  const t = useTranslations("settings");
  const { theme, setTheme, mounted } = useTheme();
  const locale = useLocale();
  const router = useRouter();

  const currentLocale = LOCALES.find((l) => l.code === locale) || LOCALES[0];

  const handleLocaleChange = (newLocale: string) => {
    // eslint-disable-next-line react-hooks/immutability
    document.cookie = `locale=${newLocale};path=/;max-age=31536000`;
    router.refresh();
  };

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-base font-semibold text-foreground">
          {t("general.title")}
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          {t("general.description")}
        </p>
      </div>

      {/* Theme */}
      <div className="space-y-3">
        <label className="text-sm font-medium text-foreground">
          {t("general.theme")}
        </label>
        <div className="grid grid-cols-3 gap-2">
          {[
            { value: "auto" as const, icon: Monitor, label: t("general.themeAuto") },
            { value: "light" as const, icon: Sun, label: t("general.themeLight") },
            { value: "dark" as const, icon: Moon, label: t("general.themeDark") },
          ].map(({ value, icon: Icon, label }) => (
            <button
              key={value}
              onClick={() => setTheme(value)}
              className={cn(
                "h-10 rounded-lg flex items-center justify-center gap-2",
                "text-sm font-medium transition-colors",
                "cursor-pointer",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
                mounted && theme === value
                  ? "bg-primary text-primary-foreground"
                  : "bg-secondary text-muted-foreground hover:text-foreground"
              )}
            >
              <Icon className="w-4 h-4" />
              <span>{label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Language */}
      <div className="space-y-3">
        <label className="text-sm font-medium text-foreground">
          {t("general.language")}
        </label>
        <div className="grid grid-cols-2 gap-2">
          {LOCALES.map((loc) => (
            <button
              key={loc.code}
              onClick={() => handleLocaleChange(loc.code)}
              className={cn(
                "h-10 rounded-lg flex items-center justify-center gap-2",
                "text-sm font-medium transition-colors",
                "cursor-pointer",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
                currentLocale.code === loc.code
                  ? "bg-primary text-primary-foreground"
                  : "bg-secondary text-muted-foreground hover:text-foreground"
              )}
            >
              <Globe className="w-4 h-4" />
              <span>{loc.label}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
