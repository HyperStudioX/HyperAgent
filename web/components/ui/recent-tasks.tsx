"use client";

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import {
  MessageCircle,
  Search,
  Trash2,
  Sparkles,
  Loader2,
  CheckCircle2,
  AlertCircle,
  GraduationCap,
  TrendingUp,
  Code2,
  Newspaper,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { Conversation, ResearchScenario } from "@/lib/types";
import type { ResearchTask } from "@/lib/stores/task-store";

// Unified item type
export type RecentItem =
  | { type: "conversation"; data: Conversation }
  | { type: "task"; data: ResearchTask };

const SCENARIO_ICONS: Record<ResearchScenario, React.ReactNode> = {
  academic: <GraduationCap className="w-2.5 h-2.5" />,
  market: <TrendingUp className="w-2.5 h-2.5" />,
  technical: <Code2 className="w-2.5 h-2.5" />,
  news: <Newspaper className="w-2.5 h-2.5" />,
};

// Group items by time period
function groupByTimePeriod(items: RecentItem[]): Record<string, RecentItem[]> {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);
  const lastWeek = new Date(today.getTime() - 7 * 86400000);

  const groups: Record<string, RecentItem[]> = {
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

interface RecentTasksProps {
  conversations: Conversation[];
  tasks: ResearchTask[];
  activeConversationId: string | null;
  activeTaskId: string | null;
  onSelect: (item: RecentItem) => void;
  onDelete: (item: RecentItem) => void;
  className?: string;
}

export function RecentTasks({
  conversations,
  tasks,
  activeConversationId,
  activeTaskId,
  onSelect,
  onDelete,
  className,
}: RecentTasksProps) {
  const t = useTranslations("sidebar");

  // Combine and sort items
  const allItems = useMemo(() => {
    const conversationItems: RecentItem[] = conversations.map((conv) => ({
      type: "conversation" as const,
      data: conv,
    }));
    const taskItems: RecentItem[] = tasks.map((task) => ({
      type: "task" as const,
      data: task,
    }));
    return [...conversationItems, ...taskItems].sort(
      (a, b) =>
        new Date(b.data.updatedAt).getTime() -
        new Date(a.data.updatedAt).getTime()
    );
  }, [conversations, tasks]);

  const groupedItems = useMemo(
    () => groupByTimePeriod(allItems),
    [allItems]
  );

  // Format relative time
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

  const periodLabels: Record<string, string> = {
    today: t("today"),
    yesterday: t("yesterday"),
    thisWeek: t("thisWeek"),
    earlier: t("earlier"),
  };

  return (
    <div className={cn("flex flex-col", className)}>
      {/* Header */}
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

      {/* List */}
      <div className="flex-1 overflow-y-auto px-2 md:px-3 pb-3">
        {allItems.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="space-y-4">
            {Object.entries(groupedItems).map(
              ([period, items]) =>
                items.length > 0 && (
                  <TimeGroup
                    key={period}
                    label={periodLabels[period]}
                    items={items}
                    activeConversationId={activeConversationId}
                    activeTaskId={activeTaskId}
                    onSelect={onSelect}
                    onDelete={onDelete}
                    formatRelativeTime={formatRelativeTime}
                  />
                )
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// Empty state component
function EmptyState() {
  const t = useTranslations("sidebar");
  return (
    <div className="flex flex-col items-center justify-center py-12 px-4">
      <div className="w-12 h-12 rounded-2xl bg-secondary/50 flex items-center justify-center mb-4">
        <MessageCircle className="w-5 h-5 text-muted-foreground/60" />
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
  items: RecentItem[];
  activeConversationId: string | null;
  activeTaskId: string | null;
  onSelect: (item: RecentItem) => void;
  onDelete: (item: RecentItem) => void;
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
            <RecentItemRow
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

// Individual item row component
interface RecentItemRowProps {
  item: RecentItem;
  isActive: boolean;
  isLast: boolean;
  onClick: () => void;
  onDelete: () => void;
  formatRelativeTime: (date: Date) => string;
}

function RecentItemRow({
  item,
  isActive,
  isLast,
  onClick,
  onDelete,
  formatRelativeTime,
}: RecentItemRowProps) {
  const t = useTranslations("sidebar");
  const isTask = item.type === "task";
  const isResearch =
    isTask || (item.type === "conversation" && item.data.type === "research");
  const title = isTask ? item.data.query : item.data.title;
  const taskStatus = isTask ? item.data.status : null;

  return (
    <div
      className={cn(
        "group relative flex items-start gap-3 pl-1 pr-2 py-2 rounded-lg cursor-pointer transition-all duration-150",
        isActive ? "bg-secondary" : "hover:bg-secondary/50"
      )}
      onClick={onClick}
    >
      {/* Timeline dot - encodes status in color/animation */}
      <div className="relative z-10 mt-1.5">
        <div
          className={cn(
            "w-2.5 h-2.5 rounded-full border-2 transition-all",
            // Active item
            isActive && "border-foreground bg-foreground shadow-md",
            // Running task - pulsing animation
            !isActive && taskStatus === "running" && "border-blue-500 bg-blue-500/40 animate-pulse",
            // Completed
            !isActive && taskStatus === "completed" && "border-green-500/70 bg-green-500/20",
            // Failed
            !isActive && taskStatus === "failed" && "border-red-500/70 bg-red-500/20",
            // Research (no specific status)
            !isActive && !taskStatus && isResearch && "border-blue-500/60 bg-blue-500/20 group-hover:border-blue-500",
            // Chat (default)
            !isActive && !taskStatus && !isResearch && "border-muted-foreground/40 bg-muted-foreground/10 group-hover:border-muted-foreground/60"
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
                {SCENARIO_ICONS[(item.data as ResearchTask).scenario]}
                <span>{t("research")}</span>
              </>
            ) : isResearch ? (
              <>
                <Search className="w-2.5 h-2.5" />
                <span>{t("research")}</span>
              </>
            ) : (
              <>
                <MessageCircle className="w-2.5 h-2.5" />
                <span>{t("chat")}</span>
              </>
            )}
          </div>

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
