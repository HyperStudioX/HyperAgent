"use client";

import { useEffect, useState, useDeferredValue } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Search, Loader2, AlertCircle, FolderOpen, Plus } from "lucide-react";
import { cn } from "@/lib/utils";
import { useProjectStore } from "@/lib/stores/project-store";
import { ProjectCard } from "./project-card";
import { CreateProjectDialog } from "./create-project-dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export function ProjectBrowser() {
  const t = useTranslations("projects");
  const router = useRouter();
  const { projects, isLoading, loadProjects, createProject } =
    useProjectStore();

  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const deferredSearch = useDeferredValue(searchQuery);

  useEffect(() => {
    loadProjectsData();
  }, []);

  async function loadProjectsData() {
    try {
      setError(null);
      await loadProjects();
    } catch {
      setError(t("loadError"));
    }
  }

  const filteredProjects = projects.filter((project) => {
    if (!deferredSearch) return true;
    const q = deferredSearch.toLowerCase();
    return (
      project.name.toLowerCase().includes(q) ||
      project.description?.toLowerCase().includes(q)
    );
  });

  const handleCreate = async (data: {
    name: string;
    description?: string;
    color?: string;
  }) => {
    try {
      const id = await createProject(data);
      setShowCreateDialog(false);
      router.push(`/projects/${id}`);
    } catch (err) {
      console.error("Failed to create project:", err);
    }
  };

  if (isLoading && projects.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-3">
        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
        <p className="text-sm text-muted-foreground">Loading projects...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-3">
        <div className="w-10 h-10 rounded-full bg-destructive/10 flex items-center justify-center">
          <AlertCircle className="w-5 h-5 text-destructive" />
        </div>
        <p className="text-sm text-muted-foreground">{error}</p>
        <button
          onClick={loadProjectsData}
          className="text-sm text-foreground font-medium underline underline-offset-4 hover:text-foreground/80 cursor-pointer"
        >
          {t("retry")}
        </button>
      </div>
    );
  }

  if (projects.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-3">
        <div className="w-10 h-10 rounded-full bg-secondary flex items-center justify-center">
          <FolderOpen className="w-5 h-5 text-muted-foreground" />
        </div>
        <p className="text-sm font-medium text-foreground">
          {t("noProjects")}
        </p>
        <p className="text-sm text-muted-foreground">
          {t("noProjectsDescription")}
        </p>
        <Button
          onClick={() => setShowCreateDialog(true)}
          className="mt-2 cursor-pointer"
        >
          <Plus className="w-4 h-4 mr-1.5" />
          {t("createProject")}
        </Button>
        <CreateProjectDialog
          open={showCreateDialog}
          onClose={() => setShowCreateDialog(false)}
          onSubmit={handleCreate}
        />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Search and create */}
      <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
          <Input
            placeholder={t("search")}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 h-9"
          />
        </div>
        <Button
          onClick={() => setShowCreateDialog(true)}
          size="sm"
          className="cursor-pointer"
        >
          <Plus className="w-4 h-4 mr-1.5" />
          {t("createProject")}
        </Button>
      </div>

      {/* Count */}
      <div className="text-xs text-muted-foreground">
        {t("projectCount", { count: filteredProjects.length })}
      </div>

      {/* Grid */}
      {filteredProjects.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 gap-2">
          <Search className="w-5 h-5 text-muted-foreground/50" />
          <p className="text-sm text-muted-foreground">{t("noResults")}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {filteredProjects.map((project, idx) => (
            <ProjectCard key={project.id} project={project} index={idx} />
          ))}
        </div>
      )}

      <CreateProjectDialog
        open={showCreateDialog}
        onClose={() => setShowCreateDialog(false)}
        onSubmit={handleCreate}
      />
    </div>
  );
}
