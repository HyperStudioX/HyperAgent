"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import {
  Brain,
  Plus,
  Pencil,
  Trash2,
  X,
  Check,
  AlertCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useSettingsStore } from "@/lib/stores/settings-store";

interface Memory {
  id: string;
  type: string;
  content: string;
  metadata: Record<string, unknown>;
  created_at: number;
  access_count: number;
}

const MEMORY_TYPES = ["preference", "fact", "episodic", "procedural"] as const;
type MemoryType = (typeof MEMORY_TYPES)[number];

const TYPE_FILTER_KEYS: Record<string, string> = {
  all: "typeAll",
  preference: "typePreference",
  fact: "typeFact",
  episodic: "typeEpisodic",
  procedural: "typeProcedural",
};

async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`/api/v1${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json() as Promise<T>;
}

export function MemorySection() {
  const t = useTranslations("settings");
  const { memoryEnabled, setMemoryEnabled } = useSettingsStore();

  const [memories, setMemories] = useState<Memory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>("all");

  // Add form state
  const [showAddForm, setShowAddForm] = useState(false);
  const [newType, setNewType] = useState<MemoryType>("fact");
  const [newContent, setNewContent] = useState("");
  const [saving, setSaving] = useState(false);

  // Edit state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");

  // Clear all confirmation
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  const fetchMemories = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await apiFetch<{ memories: Memory[] }>("/memory");
      setMemories(data.memories);
    } catch {
      setError(t("memory.loadError"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    fetchMemories();
  }, [fetchMemories]);

  const handleAdd = async () => {
    if (!newContent.trim()) return;
    try {
      setSaving(true);
      const entry = await apiFetch<Memory>("/memory", {
        method: "POST",
        body: JSON.stringify({ type: newType, content: newContent.trim() }),
      });
      setMemories((prev) => [entry, ...prev]);
      setNewContent("");
      setShowAddForm(false);
    } catch {
      setError(t("memory.saveError"));
    } finally {
      setSaving(false);
    }
  };

  const handleUpdate = async (id: string) => {
    if (!editContent.trim()) return;
    try {
      const updated = await apiFetch<Memory>(`/memory/${id}`, {
        method: "PUT",
        body: JSON.stringify({ content: editContent.trim() }),
      });
      setMemories((prev) =>
        prev.map((m) => (m.id === id ? updated : m))
      );
      setEditingId(null);
    } catch {
      setError(t("memory.saveError"));
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await apiFetch(`/memory/${id}`, { method: "DELETE" });
      setMemories((prev) => prev.filter((m) => m.id !== id));
    } catch {
      setError(t("memory.deleteError"));
    }
  };

  const handleClearAll = async () => {
    try {
      await Promise.all(
        memories.map((m) =>
          apiFetch(`/memory/${m.id}`, { method: "DELETE" })
        )
      );
      setMemories([]);
      setShowClearConfirm(false);
    } catch {
      setError(t("memory.deleteError"));
    }
  };

  const filtered =
    filter === "all" ? memories : memories.filter((m) => m.type === filter);

  const formatDate = (ts: number) => {
    const date = new Date(ts * 1000);
    return date.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-base font-semibold text-foreground">
          {t("memory.title")}
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          {t("memory.description")}
        </p>
      </div>

      {/* Enable/disable toggle */}
      <label className="flex items-center justify-between py-2 cursor-pointer">
        <span className="text-sm text-foreground">
          {t("memory.enableToggle")}
        </span>
        <button
          role="switch"
          aria-checked={memoryEnabled}
          onClick={() => setMemoryEnabled(!memoryEnabled)}
          className={cn(
            "relative inline-flex h-5 w-9 shrink-0 rounded-full transition-colors cursor-pointer",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
            memoryEnabled ? "bg-primary" : "bg-secondary"
          )}
        >
          <span
            className={cn(
              "pointer-events-none block h-4 w-4 rounded-full bg-white shadow-sm transition-transform mt-0.5",
              memoryEnabled ? "translate-x-[18px]" : "translate-x-0.5"
            )}
          />
        </button>
      </label>

      {/* Error banner */}
      {error && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-destructive/10 text-destructive text-sm">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
          <button
            onClick={() => setError(null)}
            className="ml-auto p-0.5 hover:bg-destructive/20 rounded cursor-pointer"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Type filter */}
      <div className="flex flex-wrap gap-2">
        {Object.entries(TYPE_FILTER_KEYS).map(([key, tKey]) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={cn(
              "h-8 px-3 rounded-lg text-sm font-medium transition-colors cursor-pointer",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
              filter === key
                ? "bg-primary text-primary-foreground"
                : "bg-secondary text-muted-foreground hover:text-foreground"
            )}
          >
            {t(`memory.${tKey}` as `memory.${string}`)}
          </button>
        ))}
      </div>

      {/* Actions bar */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => setShowAddForm((v) => !v)}
          className={cn(
            "h-8 px-3 rounded-lg text-sm font-medium transition-colors cursor-pointer",
            "flex items-center gap-1.5",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
            "bg-secondary text-muted-foreground hover:text-foreground"
          )}
        >
          <Plus className="w-3.5 h-3.5" />
          {t("memory.addMemory")}
        </button>
        {memories.length > 0 && (
          <button
            onClick={() => setShowClearConfirm(true)}
            className={cn(
              "h-8 px-3 rounded-lg text-sm font-medium transition-colors cursor-pointer",
              "flex items-center gap-1.5 ml-auto",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
              "text-destructive hover:bg-destructive/10"
            )}
          >
            <Trash2 className="w-3.5 h-3.5" />
            {t("memory.clearAll")}
          </button>
        )}
      </div>

      {/* Clear all confirmation */}
      {showClearConfirm && (
        <div className="flex items-center gap-3 px-3 py-2.5 rounded-lg border border-destructive/30 bg-destructive/5">
          <span className="text-sm text-foreground flex-1">
            {t("memory.clearAllConfirm")}
          </span>
          <button
            onClick={handleClearAll}
            className="h-7 px-3 rounded-md text-xs font-medium bg-destructive text-destructive-foreground hover:bg-destructive/90 cursor-pointer"
          >
            {t("memory.clearAllButton")}
          </button>
          <button
            onClick={() => setShowClearConfirm(false)}
            className="h-7 px-2 rounded-md text-xs text-muted-foreground hover:text-foreground cursor-pointer"
          >
            {t("memory.cancelEdit")}
          </button>
        </div>
      )}

      {/* Add form */}
      {showAddForm && (
        <div className="space-y-3 p-4 rounded-lg border border-border bg-secondary/30">
          <div className="text-sm font-medium text-foreground">
            {t("memory.addTitle")}
          </div>
          <div className="flex gap-2">
            {MEMORY_TYPES.map((mt) => (
              <button
                key={mt}
                onClick={() => setNewType(mt)}
                className={cn(
                  "h-7 px-2.5 rounded-md text-xs font-medium transition-colors cursor-pointer",
                  newType === mt
                    ? "bg-primary text-primary-foreground"
                    : "bg-secondary text-muted-foreground hover:text-foreground"
                )}
              >
                {t(
                  `memory.${TYPE_FILTER_KEYS[mt]}` as `memory.${string}`
                )}
              </button>
            ))}
          </div>
          <textarea
            value={newContent}
            onChange={(e) => setNewContent(e.target.value)}
            placeholder={t("memory.contentPlaceholder")}
            rows={2}
            className={cn(
              "w-full px-3 py-2 rounded-lg text-sm resize-none",
              "bg-background border border-border",
              "text-foreground placeholder:text-muted-foreground",
              "focus:outline-none focus:ring-2 focus:ring-primary"
            )}
          />
          <div className="flex justify-end gap-2">
            <button
              onClick={() => {
                setShowAddForm(false);
                setNewContent("");
              }}
              className="h-8 px-3 rounded-lg text-sm font-medium text-muted-foreground hover:text-foreground cursor-pointer"
            >
              {t("memory.cancelEdit")}
            </button>
            <button
              onClick={handleAdd}
              disabled={saving || !newContent.trim()}
              className={cn(
                "h-8 px-3 rounded-lg text-sm font-medium cursor-pointer",
                "bg-primary text-primary-foreground hover:bg-primary/90",
                "disabled:opacity-50 disabled:cursor-not-allowed"
              )}
            >
              {t("memory.saveMemory")}
            </button>
          </div>
        </div>
      )}

      {/* Memory list */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-16 rounded-lg bg-secondary animate-pulse"
            />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <div className="w-12 h-12 rounded-lg bg-secondary flex items-center justify-center mb-4">
            <Brain className="w-6 h-6 text-muted-foreground" />
          </div>
          <p className="text-sm font-medium text-foreground mb-1">
            {filter === "all"
              ? t("memory.emptyTitle")
              : t("memory.emptyFiltered")}
          </p>
          {filter === "all" && (
            <p className="text-xs text-muted-foreground max-w-xs">
              {t("memory.emptyDescription")}
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((m) => (
            <div
              key={m.id}
              className="px-4 py-3 rounded-lg border border-border bg-background"
            >
              {editingId === m.id ? (
                <div className="space-y-2">
                  <textarea
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    rows={2}
                    className={cn(
                      "w-full px-3 py-2 rounded-lg text-sm resize-none",
                      "bg-secondary border border-border",
                      "text-foreground",
                      "focus:outline-none focus:ring-2 focus:ring-primary"
                    )}
                  />
                  <div className="flex justify-end gap-1.5">
                    <button
                      onClick={() => setEditingId(null)}
                      className="h-7 px-2 rounded-md text-xs text-muted-foreground hover:text-foreground cursor-pointer"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => handleUpdate(m.id)}
                      disabled={!editContent.trim()}
                      className="h-7 px-2 rounded-md text-xs text-primary hover:bg-primary/10 cursor-pointer disabled:opacity-50"
                    >
                      <Check className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex items-start gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-foreground whitespace-pre-wrap break-words">
                      {m.content}
                    </p>
                    <div className="flex items-center gap-2 mt-1.5">
                      <span
                        className={cn(
                          "inline-flex h-5 items-center px-1.5 rounded text-[10px] font-medium",
                          "bg-secondary text-muted-foreground"
                        )}
                      >
                        {t(
                          `memory.${TYPE_FILTER_KEYS[m.type]}` as `memory.${string}`
                        )}
                      </span>
                      <span className="text-[10px] text-muted-foreground">
                        {formatDate(m.created_at)}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <button
                      onClick={() => {
                        setEditingId(m.id);
                        setEditContent(m.content);
                      }}
                      className="h-7 w-7 rounded-md flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-secondary cursor-pointer"
                      title={t("memory.editMemory")}
                    >
                      <Pencil className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => handleDelete(m.id)}
                      className="h-7 w-7 rounded-md flex items-center justify-center text-muted-foreground hover:text-destructive hover:bg-destructive/10 cursor-pointer"
                      title={t("memory.deleteMemory")}
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
