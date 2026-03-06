"use client";

import { useState, useRef, useEffect } from "react";
import Image from "next/image";
import { useTranslations } from "next-intl";
import { useAuth } from "@/lib/hooks/use-auth";
import {
  LogOut,
  User,
  Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useSettingsDialogStore } from "@/lib/stores/settings-dialog-store";

export function UserProfileMenu() {
  const { user, isAuthenticated, isLoading, login, logout } = useAuth();
  const t = useTranslations("sidebar");
  const { openSettings } = useSettingsDialogStore();

  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const handleLogout = () => {
    setIsOpen(false);
    logout();
  };

  const handleOpenSettings = () => {
    setIsOpen(false);
    openSettings();
  };

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

  // Close on escape
  useEffect(() => {
    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsOpen(false);
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
          "h-9 px-4 rounded-sm",
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
        onClick={() => setIsOpen(!isOpen)}
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
            "w-72 bg-card border border-border rounded-lg",
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
            {/* Settings */}
            <button
              onClick={handleOpenSettings}
              className={cn(
                "w-full px-4 py-2.5 flex items-center gap-3",
                "text-sm text-foreground",
                "hover:bg-secondary/50 transition-colors"
              )}
            >
              <Settings className="w-4 h-4 text-muted-foreground" />
              <span>{t("preferences")}</span>
            </button>

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
