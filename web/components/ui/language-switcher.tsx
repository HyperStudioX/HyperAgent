"use client";

import { useLocale } from "next-intl";
import { useRouter } from "next/navigation";
import { Globe } from "lucide-react";
import { cn } from "@/lib/utils";

const LOCALES = [
  { code: "en", name: "English", nativeName: "English" },
  { code: "zh-CN", name: "Chinese (Simplified)", nativeName: "简体中文" },
] as const;

interface LanguageSwitcherProps {
  className?: string;
}

export function LanguageSwitcher({ className }: LanguageSwitcherProps) {
  const locale = useLocale();
  const router = useRouter();

  const handleLocaleChange = (newLocale: string) => {
    // Set cookie to persist locale preference
    document.cookie = `locale=${newLocale};path=/;max-age=31536000`;
    // Refresh the page to apply new locale
    router.refresh();
  };

  const otherLocale =
    LOCALES.find((l) => l.code !== locale) || LOCALES[1];

  return (
    <button
      onClick={() => handleLocaleChange(otherLocale.code)}
      className={cn(
        "flex items-center justify-center gap-2 h-9 px-3 text-sm font-medium rounded-lg",
        "text-muted-foreground hover:text-foreground hover:bg-secondary/50 transition-colors",
        className
      )}
      title={otherLocale.nativeName}
    >
      <Globe className="w-4 h-4" />
    </button>
  );
}
