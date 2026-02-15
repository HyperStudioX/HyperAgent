"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  ArrowLeft,
  Loader2,
  MessageSquare,
  FileText,
  Trash2,
  Plus,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { COLOR_MAP } from "@/lib/utils/project-colors";
import { useProjectStore } from "@/lib/stores/project-store";
import { useChatStore } from "@/lib/stores/chat-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PROJECT_COLORS, type ProjectColor } from "@/lib/types/projects";

interface ProjectDetailViewProps {
  projectId: string;
}

export function ProjectDetailView({ projectId }: ProjectDetailViewProps) {
  const t = useTranslations("projects");
  const router = useRouter();

  const {
    activeProject,
    isLoading,
    loadProject,
    updateProject,
    deleteProject,
    removeItems,
    assignItems,
  } = useProjectStore();

  const conversations = useChatStore((state) => state.conversations);
  const chatHydrated = useChatStore((state) => state.hasHydrated);

  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editColor, setEditColor] = useState<ProjectColor>("blue");
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showAddItems, setShowAddItems] = useState(false);
  const [selectedConvIds, setSelectedConvIds] = useState<string[]>([]);

  useEffect(() => {
    loadProject(projectId);
  }, [projectId]);

  useEffect(() => {
    if (activeProject) {
      setEditName(activeProject.name);
      setEditDescription(activeProject.description || "");
      setEditColor((activeProject.color as ProjectColor) || "blue");
    }
  }, [activeProject]);

  const handleSave = async () => {
    if (!editName.trim()) return;
    try {
      await updateProject(projectId, {
        name: editName.trim(),
        description: editDescription.trim() || undefined,
        color: editColor,
      });
      setIsEditing(false);
    } catch (err) {
      console.error("Failed to update project:", err);
    }
  };

  const handleDelete = async () => {
    try {
      await deleteProject(projectId);
      router.push("/projects");
    } catch (err) {
      console.error("Failed to delete project:", err);
    }
  };

  const handleRemoveConversation = async (convId: string) => {
    await removeItems(projectId, { conversation_ids: [convId] });
  };

  const handleRemoveTask = async (taskId: string) => {
    await removeItems(projectId, { research_task_ids: [taskId] });
  };

  const handleAssignConversations = async () => {
    if (selectedConvIds.length === 0) return;
    await assignItems(projectId, { conversation_ids: selectedConvIds });
    setSelectedConvIds([]);
    setShowAddItems(false);
  };

  // Conversations not assigned to this project
  const unassignedConversations = chatHydrated
    ? conversations.filter(
        (c) =>
          !activeProject?.conversations.some((pc) => pc.id === c.id)
      )
    : [];

  if (isLoading && !activeProject) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-3">
        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!activeProject) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-3">
        <p className="text-sm text-muted-foreground">Project not found</p>
        <Button
          variant="ghost"
          onClick={() => router.push("/projects")}
          className="cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4 mr-1.5" />
          Back to projects
        </Button>
      </div>
    );
  }

  const colorClass = activeProject.color
    ? COLOR_MAP[activeProject.color] || "bg-muted-foreground"
    : "bg-muted-foreground";

  return (
    <div className="space-y-6">
      {/* Back button */}
      <button
        onClick={() => router.push("/projects")}
        className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
      >
        <ArrowLeft className="w-4 h-4" />
        {t("title")}
      </button>

      {/* Project header */}
      {isEditing ? (
        <div className="space-y-4 border border-border/50 rounded-xl p-4">
          <div>
            <label className="text-sm font-medium mb-1.5 block">
              {t("name")}
            </label>
            <Input
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              autoFocus
            />
          </div>
          <div>
            <label className="text-sm font-medium mb-1.5 block">
              {t("description")}
            </label>
            <textarea
              value={editDescription}
              onChange={(e) => setEditDescription(e.target.value)}
              rows={2}
              className="flex w-full rounded-lg border border-border bg-transparent px-3 py-2 text-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 resize-none"
            />
          </div>
          <div>
            <label className="text-sm font-medium mb-1.5 block">
              {t("color")}
            </label>
            <div className="flex items-center gap-2">
              {PROJECT_COLORS.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setEditColor(c)}
                  className={cn(
                    "w-6 h-6 rounded-full transition-all cursor-pointer",
                    COLOR_MAP[c],
                    editColor === c
                      ? "ring-2 ring-offset-2 ring-foreground ring-offset-card scale-110"
                      : "hover:scale-110"
                  )}
                />
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button onClick={handleSave} size="sm" className="cursor-pointer">
              {t("save")}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsEditing(false)}
              className="cursor-pointer"
            >
              {t("cancel")}
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-3">
            <div className={cn("w-4 h-4 rounded-full mt-1", colorClass)} />
            <div>
              <h1 className="text-2xl font-bold">{activeProject.name}</h1>
              {activeProject.description && (
                <p className="text-muted-foreground mt-1">
                  {activeProject.description}
                </p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsEditing(true)}
              className="cursor-pointer"
            >
              {t("editProject")}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowDeleteConfirm(true)}
              className="text-destructive hover:text-destructive cursor-pointer"
            >
              <Trash2 className="w-4 h-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Delete confirmation */}
      {showDeleteConfirm && (
        <div className="border border-destructive/50 rounded-xl p-4 bg-destructive/5">
          <p className="text-sm text-foreground">{t("deleteConfirm")}</p>
          <div className="flex items-center gap-2 mt-3">
            <Button
              variant="destructive"
              size="sm"
              onClick={handleDelete}
              className="cursor-pointer"
            >
              {t("deleteProject")}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowDeleteConfirm(false)}
              className="cursor-pointer"
            >
              {t("cancel")}
            </Button>
          </div>
        </div>
      )}

      {/* Conversations section */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide flex items-center gap-2">
            <MessageSquare className="w-4 h-4" />
            {t("conversations")}
            <span className="text-xs text-muted-foreground font-normal">
              ({activeProject.conversations.length})
            </span>
          </h2>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowAddItems(true)}
            className="cursor-pointer"
          >
            <Plus className="w-4 h-4 mr-1" />
            {t("addItems")}
          </Button>
        </div>

        {activeProject.conversations.length === 0 ? (
          <p className="text-sm text-muted-foreground py-4">
            {t("noConversations")}
          </p>
        ) : (
          <div className="space-y-1">
            {activeProject.conversations.map((conv) => (
              <div
                key={conv.id}
                className="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-secondary/30 transition-colors group"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <MessageSquare className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                  <span className="text-sm truncate">{conv.title}</span>
                  <span className="text-[10px] text-muted-foreground uppercase">
                    {conv.type}
                  </span>
                </div>
                <button
                  onClick={() => handleRemoveConversation(conv.id)}
                  className="text-xs text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-all cursor-pointer"
                >
                  {t("removeFromProject")}
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Research Tasks section */}
      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide flex items-center gap-2 mb-3">
          <FileText className="w-4 h-4" />
          {t("researchTasks")}
          <span className="text-xs text-muted-foreground font-normal">
            ({activeProject.research_tasks.length})
          </span>
        </h2>

        {activeProject.research_tasks.length === 0 ? (
          <p className="text-sm text-muted-foreground py-4">
            {t("noTasks")}
          </p>
        ) : (
          <div className="space-y-1">
            {activeProject.research_tasks.map((task) => (
              <div
                key={task.id}
                className="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-secondary/30 transition-colors group"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <FileText className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                  <span className="text-sm truncate">{task.query}</span>
                  <span className="text-[10px] text-muted-foreground uppercase">
                    {task.status}
                  </span>
                </div>
                <button
                  onClick={() => handleRemoveTask(task.id)}
                  className="text-xs text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-all cursor-pointer"
                >
                  {t("removeFromProject")}
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Add Items Dialog */}
      {showAddItems && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setShowAddItems(false)}
            aria-hidden="true"
          />
          <div className="relative bg-card border border-border rounded-xl shadow-lg w-full max-w-md mx-4 p-6 max-h-[80vh] overflow-y-auto">
            <button
              onClick={() => setShowAddItems(false)}
              className="absolute top-4 right-4 text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>

            <h2 className="text-lg font-semibold mb-4">{t("addItems")}</h2>

            {unassignedConversations.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                {t("noConversations")}
              </p>
            ) : (
              <div className="space-y-1">
                {unassignedConversations.map((conv) => (
                  <label
                    key={conv.id}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-secondary/30 transition-colors cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={selectedConvIds.includes(conv.id)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedConvIds((prev) => [...prev, conv.id]);
                        } else {
                          setSelectedConvIds((prev) =>
                            prev.filter((id) => id !== conv.id)
                          );
                        }
                      }}
                      className="rounded"
                    />
                    <MessageSquare className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                    <span className="text-sm truncate">{conv.title}</span>
                    <span className="text-[10px] text-muted-foreground uppercase">
                      {conv.type}
                    </span>
                  </label>
                ))}
              </div>
            )}

            <div className="flex items-center justify-end gap-2 mt-4 pt-4 border-t border-border/30">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowAddItems(false)}
                className="cursor-pointer"
              >
                {t("cancel")}
              </Button>
              <Button
                size="sm"
                disabled={selectedConvIds.length === 0}
                onClick={handleAssignConversations}
                className="cursor-pointer"
              >
                {t("addItems")} ({selectedConvIds.length})
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
