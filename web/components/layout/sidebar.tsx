"use client";

import React, { useState, useEffect } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useChatStore } from "@/lib/stores/chat-store";
import { useTaskStore } from "@/lib/stores/task-store";
import { useTheme } from "@/lib/hooks/use-theme";
import { UserMenu } from "@/components/auth/user-menu";
import { PreferencesPanel } from "@/components/ui/preferences-panel";
import { RecentTasks, type RecentItem } from "@/components/ui/recent-tasks";
import { CreateMenu } from "@/components/ui/create-menu";

interface SidebarProps {
  className?: string;
  isOpen?: boolean;
  onClose?: () => void;
}

export function Sidebar({ className, isOpen = true, onClose }: SidebarProps) {
  const router = useRouter();
  const {
    conversations,
    activeConversationId,
    hasHydrated: chatHydrated,
    setActiveConversation,
  } = useChatStore();
  const {
    tasks,
    activeTaskId,
    hasHydrated: taskHydrated,
    setActiveTask,
    deleteTask,
  } = useTaskStore();
  const { deleteConversation } = useChatStore();

  const hasHydrated = chatHydrated && taskHydrated;
  const { theme, setTheme, mounted } = useTheme();

  // Close sidebar on mobile when clicking outside
  useEffect(() => {
    if (!isOpen) return;

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && onClose) {
        onClose();
      }
    };

    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isOpen, onClose]);

  const handleItemSelect = (item: RecentItem) => {
    if (item.type === "conversation") {
      setActiveConversation(item.data.id);
      setActiveTask(null);
      router.push("/");
    } else {
      setActiveTask(item.data.id);
      setActiveConversation(null);
      router.push(`/task/${item.data.id}`);
    }
    // Close mobile sidebar after selection
    if (onClose && window.innerWidth < 768) {
      onClose();
    }
  };

  const handleItemDelete = (item: RecentItem) => {
    if (item.type === "conversation") {
      deleteConversation(item.data.id);
    } else {
      deleteTask(item.data.id);
    }
  };

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && onClose && (
        <div
          className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40 md:hidden transition-opacity"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "h-full flex flex-col bg-card border-border",
          // Desktop: fixed width sidebar
          "md:w-80 md:border-r md:relative",
          // Mobile: full-screen overlay
          "fixed inset-y-0 left-0 z-50 w-[85vw] max-w-sm border-r",
          "transition-transform duration-300 ease-out",
          "md:translate-x-0", // Always visible on desktop
          isOpen ? "translate-x-0" : "-translate-x-full", // Slide in/out on mobile
          className
        )}
      >
      {/* Logo */}
      <div className="h-14 px-4 flex items-center justify-between border-b border-border">
        <div className="flex items-center gap-2">
          <Image
            src="/images/logo-dark.svg"
            alt="HyperAgent"
            width={28}
            height={28}
            className="dark:hidden rounded-lg"
          />
          <Image
            src="/images/logo-light.svg"
            alt="HyperAgent"
            width={28}
            height={28}
            className="hidden dark:block rounded-lg"
          />
          <span className="font-semibold text-foreground tracking-tight">HyperAgent</span>
        </div>

        {/* Mobile close button */}
        {onClose && (
          <button
            onClick={onClose}
            className="md:hidden p-2 -mr-2 text-muted-foreground hover:text-foreground rounded-lg hover:bg-secondary transition-colors"
            aria-label="Close sidebar"
          >
            <X className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* Create Menu */}
      <div className="p-3">
        <CreateMenu
          onCreate={() => {
            setActiveConversation(null);
            setActiveTask(null);
            router.push("/");
          }}
        />
      </div>

      {/* Recent Tasks */}
      {hasHydrated && (
        <RecentTasks
          conversations={conversations}
          tasks={tasks}
          activeConversationId={activeConversationId}
          activeTaskId={activeTaskId}
          onSelect={handleItemSelect}
          onDelete={handleItemDelete}
          className="flex-1 min-h-0"
        />
      )}

      {/* Footer with Preferences and User Menu */}
      <div className="p-3 border-t border-border space-y-3">
        {/* Preferences Panel */}
        <PreferencesPanel
          theme={theme}
          mounted={mounted}
          onThemeChange={setTheme}
        />

        {/* User Section */}
        <UserMenu />
      </div>
    </aside>
    </>
  );
}
