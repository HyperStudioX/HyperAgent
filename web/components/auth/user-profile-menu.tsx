"use client";

import { useState, useRef, useEffect } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useTranslations, useLocale } from "next-intl";
import { useAuth } from "@/lib/hooks/use-auth";
import { useTheme } from "@/lib/hooks/use-theme";
import {
  LogOut,
  User,
  Sun,
  Moon,
  Monitor,
  Globe,
  ChevronDown,
  Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";

const LOCALES = [
  { code: "en", label: "English", shortLabel: "EN" },
  { code: "zh-CN", label: "简体中文", shortLabel: "中文" },
] as const;

export function UserProfileMenu() {
  const { user, isAuthenticated, isLoading, login, logout } = useAuth();
  const { theme, setTheme, mounted } = useTheme();
  const t = useTranslations("sidebar");
  const locale = useLocale();
  const router = useRouter();

  const [isOpen, setIsOpen] = useState(false);
  const [showPreferences, setShowPreferences] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const currentLocale = LOCALES.find((l) => l.code === locale) || LOCALES[0];

  const handleLocaleChange = (newLocale: string) => {
    setTimeout(() => {
      document.cookie = `locale=${newLocale};path=/;max-age=31536000`;
    }, 0);
    setIsOpen(false);
    setShowPreferences(false);
    router.refresh();
  };

  const handleThemeChange = (newTheme: "light" | "dark" | "auto") => {
    setTheme(newTheme);
  };

  const handleLogout = () => {
    setIsOpen(false);
    logout();
  };

  // Close menu when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setShowPreferences(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Close on escape
  useEffect(() => {
    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsOpen(false);
        setShowPreferences(false);
      }
    }

    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, []);

  if (isLoading) {
    return (
      <div className="w-10 h-10 rounded-full bg-secondary border border-border animate-pulse" />
    );
  }

  if (!isAuthenticated) {
    return (
      <button
        onClick={login}
        className={cn(
          "h-9 px-4 rounded-lg",
          "text-sm font-medium",
          "bg-foreground text-background",
          "hover:bg-foreground/90",
          "transition-colors"
        )}
      >
        {t("signIn")}
      </button>
    );
  }

  return (
    <div ref={menuRef} className="relative">
      {/* Avatar Trigger - enhanced with border and background for visibility */}
      <button
        onClick={() => {
          setIsOpen(!isOpen);
          if (!isOpen) setShowPreferences(false);
        }}
        className={cn(
          "relative flex items-center justify-center",
          "w-10 h-10 rounded-full",
          "bg-secondary/80 border-2 border-border",
          "hover:bg-secondary hover:border-foreground/20",
          "transition-colors",
          "focus:outline-none focus-visible:ring-2 focus-visible:ring-foreground/20 focus-visible:ring-offset-2",
          isOpen && "bg-secondary border-foreground/30"
        )}
        aria-label="User menu"
      >
        {user?.image ? (
          <Image
            src={user.image}
            alt={user.name || "User"}
            width={32}
            height={32}
            loading="eager"
            unoptimized
            className="w-8 h-8 rounded-full object-cover"
          />
        ) : (
          <User className="w-4 h-4 text-muted-foreground" />
        )}
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div
          className={cn(
            "absolute top-full right-0 mt-2 z-50",
            "w-72 bg-card border border-border rounded-xl",
            "overflow-hidden animate-scale-in"
          )}
        >
          {/* User Info Header - enhanced with subtle background */}
          <div className="px-4 py-4 border-b border-border bg-secondary/30">
            <div className="flex items-center gap-3">
              {user?.image ? (
                <div className="relative">
                  <Image
                    src={user.image}
                    alt={user.name || "User"}
                    width={44}
                    height={44}
                    unoptimized
                    className="w-11 h-11 rounded-full border-2 border-border"
                  />
                </div>
              ) : (
                <div className="w-11 h-11 rounded-full bg-muted border-2 border-border flex items-center justify-center">
                  <User className="w-5 h-5 text-muted-foreground" />
                </div>
              )}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-foreground truncate">
                  {user?.name || "User"}
                </p>
                {user?.email && (
                  <p className="text-xs text-muted-foreground truncate mt-0.5">
                    {user.email}
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Menu Items */}
          <div className="py-1">
            {/* Preferences - expandable inline */}
            <div>
              <button
                onClick={() => setShowPreferences(!showPreferences)}
                className={cn(
                  "w-full px-4 py-2.5 flex items-center justify-between",
                  "text-sm text-foreground",
                  "hover:bg-secondary/50 transition-colors",
                  showPreferences && "bg-secondary/30"
                )}
              >
                <div className="flex items-center gap-3">
                  <Settings className="w-4 h-4 text-muted-foreground" />
                  <span>{t("preferences")}</span>
                </div>
                <ChevronDown
                  className={cn(
                    "w-4 h-4 text-muted-foreground transition-transform",
                    showPreferences && "rotate-180"
                  )}
                />
              </button>

              {/* Preferences Content - inline expandable */}
              {showPreferences && (
                <div className="px-4 pb-3 pt-1 space-y-3 border-t border-border/50">
                  {/* Theme Section */}
                  <div>
                    <div className="pb-2 pt-2">
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
                          onClick={() =>
                            handleThemeChange(value as "light" | "dark" | "auto")
                          }
                          className={cn(
                            "flex-1 h-8 rounded-lg flex items-center justify-center gap-1.5",
                            "text-xs font-medium transition-colors",
                            mounted && theme === value
                              ? "bg-foreground text-background"
                              : "text-muted-foreground hover:text-foreground hover:bg-secondary"
                          )}
                        >
                          <Icon className="w-3.5 h-3.5" />
                          <span>{label}</span>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Language Section */}
                  <div>
                    <div className="pb-2">
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

            {/* Divider */}
            <div className="my-1 border-t border-border" />

            {/* Sign Out */}
            <button
              onClick={handleLogout}
              className={cn(
                "w-full px-4 py-2.5 flex items-center gap-3",
                "text-sm text-destructive",
                "hover:bg-destructive/10 transition-colors"
              )}
            >
              <LogOut className="w-4 h-4" />
              <span>{t("signOut")}</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
