"use client";

import React, { useMemo } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  MessageSquare,
  Search,
  Plus,
  Trash2,
  Sun,
  Moon,
  Sparkles,
  Loader2,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useChatStore } from "@/lib/stores/chat-store";
import { useTaskStore, type ResearchTask } from "@/lib/stores/task-store";
import { useTheme } from "@/lib/hooks/use-theme";
import { LanguageSwitcher } from "@/components/ui/language-switcher";
import type { Conversation } from "@/lib/types";

interface SidebarProps {
  className?: string;
}

// Unified item type for sidebar
type SidebarItem =
  | { type: "conversation"; data: Conversation }
  | { type: "task"; data: ResearchTask };

// Group items by time period with translation keys
function groupByTimePeriod(items: SidebarItem[]): Record<string, SidebarItem[]> {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);
  const lastWeek = new Date(today.getTime() - 7 * 86400000);

  const groups: Record<string, SidebarItem[]> = {
    today: [],
    yesterday: [],
    thisWeek: [],
    earlier: [],
  };

  items.forEach((item) => {
    const itemDate = new Date(item.data.updatedAt);
    if (itemDate >= today) {
      groups.today.push(item);
    } else if (itemDate >= yesterday) {
      groups.yesterday.push(item);
    } else if (itemDate >= lastWeek) {
      groups.thisWeek.push(item);
    } else {
      groups.earlier.push(item);
    }
  });

  return groups;
}

export function Sidebar({ className }: SidebarProps) {
  const router = useRouter();
  const t = useTranslations("sidebar");
  const {
    conversations,
    activeConversationId,
    hasHydrated: chatHydrated,
    setActiveConversation,
    deleteConversation,
    createConversation,
  } = useChatStore();
  const {
    tasks,
    activeTaskId,
    hasHydrated: taskHydrated,
    setActiveTask,
    deleteTask,
  } = useTaskStore();

  const hasHydrated = chatHydrated && taskHydrated;
  const { theme, toggleTheme, mounted } = useTheme();

  // Combine conversations and tasks into unified items (only after hydration)
  const allItems = useMemo(() => {
    // Only include items after stores have hydrated to prevent hydration mismatch
    if (!hasHydrated) {
      return [];
    }

    const conversationItems: SidebarItem[] = conversations.map((conv) => ({
      type: "conversation" as const,
      data: conv,
    }));
    const taskItems: SidebarItem[] = tasks.map((task) => ({
      type: "task" as const,
      data: task,
    }));
    const items = [...conversationItems, ...taskItems].sort((a, b) =>
      new Date(b.data.updatedAt).getTime() - new Date(a.data.updatedAt).getTime()
    );
    return items;
  }, [conversations, tasks, hasHydrated]);

  const groupedItems = useMemo(
    () => groupByTimePeriod(allItems),
    [allItems]
  );

  const handleItemSelect = (item: SidebarItem) => {
    if (item.type === "conversation") {
      setActiveConversation(item.data.id);
      setActiveTask(null);
      router.push("/");
    } else {
      setActiveTask(item.data.id);
      setActiveConversation(null);
      router.push(`/task/${item.data.id}`);
    }
  };

  const handleItemDelete = (item: SidebarItem) => {
    if (item.type === "conversation") {
      deleteConversation(item.data.id);
    } else {
      deleteTask(item.data.id);
    }
  };

  // Helper to format relative time with translations
  const formatRelativeTime = (date: Date): string => {
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return t("justNow");
    if (diffMins < 60) return t("minutesAgo", { minutes: diffMins });
    if (diffHours < 24) return t("hoursAgo", { hours: diffHours });
    if (diffDays < 7) return t("daysAgo", { days: diffDays });
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  };

  // Map period keys to translations
  const periodLabels: Record<string, string> = {
    today: t("today"),
    yesterday: t("yesterday"),
    thisWeek: t("thisWeek"),
    earlier: t("earlier"),
  };

  return (
    <aside
      className={cn(
        "w-80 h-full flex flex-col bg-card border-r border-border",
        className
      )}
    >
      {/* Logo */}
      <div className="h-14 px-4 flex items-center border-b border-border">
        <div className="flex items-center gap-2">
          <Image
            src="/images/logo-light.svg"
            alt="HyperAgent"
            width={28}
            height={28}
            className="dark:hidden rounded-lg"
          />
          <Image
            src="/images/logo-dark.svg"
            alt="HyperAgent"
            width={28}
            height={28}
            className="hidden dark:block rounded-lg"
          />
          <span className="font-semibold text-foreground tracking-tight">HyperAgent</span>
        </div>
      </div>

      {/* New conversation button */}
      <div className="p-3">
        <button
          onClick={() => {
            // Clear active states to show fresh chat interface
            setActiveConversation(null);
            setActiveTask(null);
            router.push("/");
          }}
          className="group w-full flex items-center justify-center gap-2 h-10 px-4 text-sm font-medium rounded-xl
                     bg-gradient-to-r from-foreground to-foreground/90 text-background
                     hover:from-foreground/90 hover:to-foreground/80
                     shadow-sm hover:shadow-md transition-all duration-200
                     active:scale-[0.98]"
        >
          <Plus className="w-4 h-4 transition-transform group-hover:rotate-90 duration-200" />
          <span>{t("create")}</span>
        </button>
      </div>

      {/* Recent Tasks Header */}
      <div className="px-4 py-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="w-3.5 h-3.5 text-muted-foreground/60" />
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            {t("recentTasks")}
          </span>
        </div>
        <span className="text-[10px] text-muted-foreground/50 tabular-nums">
          {allItems.length}
        </span>
      </div>

      {/* Unified Timeline */}
      <div className="flex-1 overflow-y-auto px-3 pb-3">
        {allItems.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="space-y-4">
            {Object.entries(groupedItems).map(([period, items]) =>
              items.length > 0 && (
                <TimeGroup
                  key={period}
                  label={periodLabels[period]}
                  items={items}
                  activeConversationId={activeConversationId}
                  activeTaskId={activeTaskId}
                  onSelect={handleItemSelect}
                  onDelete={handleItemDelete}
                  formatRelativeTime={formatRelativeTime}
                />
              )
            )}
          </div>
        )}
      </div>

      {/* Footer with Language and Theme toggles */}
      <div className="p-3 border-t border-border">
        <div className="flex items-center gap-1">
          <LanguageSwitcher className="flex-1" />
          <button
            onClick={toggleTheme}
            className="flex-1 flex items-center justify-center gap-2 h-9 px-3 text-sm font-medium rounded-lg
                       text-muted-foreground hover:text-foreground hover:bg-secondary/50 transition-colors"
          >
            {mounted && (
              theme === "dark" ? (
                <Sun className="w-4 h-4" />
              ) : (
                <Moon className="w-4 h-4" />
              )
            )}
          </button>
        </div>
      </div>
    </aside>
  );
}

// Empty state component
function EmptyState() {
  const t = useTranslations("sidebar");
  return (
    <div className="flex flex-col items-center justify-center py-12 px-4">
      <div className="w-12 h-12 rounded-2xl bg-secondary/50 flex items-center justify-center mb-4">
        <MessageSquare className="w-5 h-5 text-muted-foreground/60" />
      </div>
      <p className="text-sm text-muted-foreground text-center mb-1">
        {t("noConversations")}
      </p>
      <p className="text-xs text-muted-foreground/60 text-center">
        {t("startChatOrResearch")}
      </p>
    </div>
  );
}

// Time group component
interface TimeGroupProps {
  label: string;
  items: SidebarItem[];
  activeConversationId: string | null;
  activeTaskId: string | null;
  onSelect: (item: SidebarItem) => void;
  onDelete: (item: SidebarItem) => void;
  formatRelativeTime: (date: Date) => string;
}

function TimeGroup({
  label,
  items,
  activeConversationId,
  activeTaskId,
  onSelect,
  onDelete,
  formatRelativeTime,
}: TimeGroupProps) {
  return (
    <div className="relative">
      {/* Time label */}
      <div className="sticky top-0 z-10 py-1.5 bg-card/95 backdrop-blur-sm">
        <span className="text-[11px] font-medium text-muted-foreground/70 tracking-wide">
          {label}
        </span>
      </div>

      {/* Timeline */}
      <div className="relative ml-2">
        {/* Vertical line */}
        <div className="absolute left-[5px] top-2 bottom-2 w-px bg-border" />

        {/* Items */}
        <div className="space-y-0.5">
          {items.map((item, index) => (
            <SidebarItemComponent
              key={item.data.id}
              item={item}
              isActive={
                item.type === "conversation"
                  ? item.data.id === activeConversationId
                  : item.data.id === activeTaskId
              }
              isLast={index === items.length - 1}
              onClick={() => onSelect(item)}
              onDelete={() => onDelete(item)}
              formatRelativeTime={formatRelativeTime}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

// Individual sidebar item component
interface SidebarItemComponentProps {
  item: SidebarItem;
  isActive: boolean;
  isLast: boolean;
  onClick: () => void;
  onDelete: () => void;
  formatRelativeTime: (date: Date) => string;
}

function SidebarItemComponent({
  item,
  isActive,
  isLast,
  onClick,
  onDelete,
  formatRelativeTime,
}: SidebarItemComponentProps) {
  const t = useTranslations("sidebar");
  const isTask = item.type === "task";
  const isResearch = isTask || (item.type === "conversation" && item.data.type === "research");
  const title = isTask ? item.data.query : item.data.title;
  const taskStatus = isTask ? item.data.status : null;

  return (
    <div
      className={cn(
        "group relative flex items-start gap-3 pl-1 pr-2 py-2 rounded-lg cursor-pointer transition-all duration-150",
        isActive
          ? "bg-secondary"
          : "hover:bg-secondary/50"
      )}
      onClick={onClick}
    >
      {/* Timeline dot */}
      <div className="relative z-10 mt-1.5">
        <div
          className={cn(
            "w-2.5 h-2.5 rounded-full border-2 transition-colors",
            isActive
              ? "border-foreground bg-foreground"
              : isResearch
                ? "border-blue-500/60 bg-blue-500/20 group-hover:border-blue-500 group-hover:bg-blue-500/40"
                : "border-muted-foreground/40 bg-muted-foreground/10 group-hover:border-muted-foreground/60"
          )}
        />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 pt-0.5">
        <div className="flex items-center gap-2 mb-0.5">
          {/* Type indicator */}
          <div
            className={cn(
              "flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium uppercase tracking-wider",
              isTask
                ? "bg-blue-500/10 text-blue-600 dark:text-blue-400"
                : isResearch
                  ? "bg-blue-500/10 text-blue-600 dark:text-blue-400"
                  : "bg-muted-foreground/10 text-muted-foreground"
            )}
          >
            {isTask ? (
              <>
                <Search className="w-2.5 h-2.5" />
                <span>{t("research")}</span>
              </>
            ) : isResearch ? (
              <>
                <Search className="w-2.5 h-2.5" />
                <span>{t("research")}</span>
              </>
            ) : (
              <>
                <MessageSquare className="w-2.5 h-2.5" />
                <span>{t("chat")}</span>
              </>
            )}
          </div>

          {/* Task status indicator */}
          {taskStatus && (
            <div className="flex items-center">
              {taskStatus === "running" && (
                <Loader2 className="w-3 h-3 text-blue-500 animate-spin" />
              )}
              {taskStatus === "completed" && (
                <CheckCircle2 className="w-3 h-3 text-green-500" />
              )}
              {taskStatus === "failed" && (
                <AlertCircle className="w-3 h-3 text-destructive" />
              )}
            </div>
          )}

          {/* Timestamp */}
          <span className="text-[10px] text-muted-foreground/50 tabular-nums">
            {formatRelativeTime(new Date(item.data.updatedAt))}
          </span>
        </div>

        {/* Title */}
        <p
          className={cn(
            "text-sm leading-snug truncate transition-colors",
            isActive ? "text-foreground font-medium" : "text-foreground/80"
          )}
        >
          {title.slice(0, 50) + (title.length > 50 ? "..." : "")}
        </p>
      </div>

      {/* Delete button */}
      <button
        className={cn(
          "absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-md transition-all",
          "opacity-0 group-hover:opacity-100",
          "hover:bg-destructive/10 hover:text-destructive"
        )}
        onClick={(e) => {
          e.stopPropagation();
          onDelete();
        }}
      >
        <Trash2 className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
