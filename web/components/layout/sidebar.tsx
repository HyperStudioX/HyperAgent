"use client";

import React, { useState, useEffect, useRef } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
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
  const { data: session, status } = useSession();
  const {
    conversations,
    activeConversationId,
    hasHydrated: chatHydrated,
    setActiveConversation,
    loadConversations,
    deleteConversation,
  } = useChatStore();
  const {
    tasks,
    activeTaskId,
    hasHydrated: taskHydrated,
    setActiveTask,
    deleteTask,
    loadTasks,
  } = useTaskStore();

  const hasHydrated = chatHydrated && taskHydrated;
  const { theme, setTheme, mounted } = useTheme();

  // Track if we've attempted to load conversations to prevent duplicate calls
  const loadAttempted = useRef(false);

  // Load conversations and tasks on mount (only load conversations if authenticated)
  useEffect(() => {
    // Wait for session to finish loading before making any decisions
    if (status === "loading") {
      return;
    }

    // If we've already attempted to load, don't try again
    if (loadAttempted.current) {
      return;
    }

    // If chat store is already hydrated, don't do anything
    if (chatHydrated) {
      return;
    }

    // Mark that we've attempted to load
    loadAttempted.current = true;

    // Only load from API if authenticated, otherwise just set hydrated
    if (status === "authenticated") {
      console.log("[Sidebar] Loading conversations from database");
      loadConversations();
    } else {
      console.log("[Sidebar] Not authenticated, using local mode");
      useChatStore.setState({ hasHydrated: true });
    }
  }, [status, chatHydrated, loadConversations]);

  // Load tasks (from API if authenticated, otherwise rely on localStorage)
  useEffect(() => {
    if (status === "loading" || taskHydrated) {
      return;
    }

    if (status === "authenticated") {
      console.log("[Sidebar] Loading tasks from database");
      loadTasks();
    } else {
      console.log("[Sidebar] Not authenticated, using local tasks only");
      useTaskStore.setState({ hasHydrated: true });
    }
  }, [status, taskHydrated, loadTasks]);

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

  const handleItemDelete = async (item: RecentItem) => {
    try {
      if (item.type === "conversation") {
        await deleteConversation(item.data.id);
      } else {
        await deleteTask(item.data.id);
      }
    } catch (error) {
      console.error("Failed to delete item:", error);
    }
  };

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && onClose && (
        <div
          className="fixed inset-0 bg-black/40 z-40 md:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "h-full flex flex-col bg-secondary/30 border-border",
          // Desktop: fixed width sidebar
          "md:w-72 md:border-r md:relative",
          // Mobile: full-screen overlay
          "fixed inset-y-0 left-0 z-50 w-[280px] border-r",
          "transition-transform duration-200",
          "md:translate-x-0", // Always visible on desktop
          isOpen ? "translate-x-0" : "-translate-x-full", // Slide in/out on mobile
          className
        )}
      >
        {/* Header */}
        <div className="h-14 px-4 flex items-center justify-between border-b border-border">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-foreground flex items-center justify-center">
              <Image
                src="/images/logo.svg"
                alt="HyperAgent"
                width={18}
                height={18}
                className="invert dark:invert-0"
              />
            </div>
            <span className="font-semibold text-foreground tracking-tight">HyperAgent</span>
          </div>

          {/* Mobile close button */}
          {onClose && (
            <button
              onClick={onClose}
              className="md:hidden p-2 -mr-2 text-muted-foreground hover:text-foreground hover:bg-secondary rounded-lg transition-colors"
              aria-label="Close sidebar"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>

        {/* Create Button */}
        <div className="px-3 py-3">
          <CreateMenu
            onCreate={() => {
              setActiveConversation(null);
              setActiveTask(null);
              router.push("/");
            }}
          />
        </div>

        {/* Recent Items */}
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

        {/* Footer */}
        <div className="px-3 py-3 border-t border-border space-y-2">
          <PreferencesPanel
            theme={theme}
            mounted={mounted}
            onThemeChange={setTheme}
          />
          <UserMenu />
        </div>
      </aside>
    </>
  );
}
