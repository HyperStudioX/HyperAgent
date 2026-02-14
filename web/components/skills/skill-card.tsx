"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { SkillMetadata } from "@/lib/types/skills";
import { Button } from "@/components/ui/button";
import { Code, Sparkles, Search, BarChart3, FileText, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";

const CATEGORY_ICONS = {
  research: Search,
  code: Code,
  data: BarChart3,
  creative: Sparkles,
  automation: FileText,
};

const CATEGORY_ACCENT = {
  research: {
    bg: "bg-blue-500/8 dark:bg-blue-500/15",
    icon: "text-blue-600 dark:text-blue-400",
    border: "group-hover:border-blue-500/20",
    tag: "bg-blue-500/8 text-blue-700 dark:text-blue-300",
  },
  code: {
    bg: "bg-emerald-500/8 dark:bg-emerald-500/15",
    icon: "text-emerald-600 dark:text-emerald-400",
    border: "group-hover:border-emerald-500/20",
    tag: "bg-emerald-500/8 text-emerald-700 dark:text-emerald-300",
  },
  data: {
    bg: "bg-amber-500/8 dark:bg-amber-500/15",
    icon: "text-amber-600 dark:text-amber-400",
    border: "group-hover:border-amber-500/20",
    tag: "bg-amber-500/8 text-amber-700 dark:text-amber-300",
  },
  creative: {
    bg: "bg-purple-500/8 dark:bg-purple-500/15",
    icon: "text-purple-600 dark:text-purple-400",
    border: "group-hover:border-purple-500/20",
    tag: "bg-purple-500/8 text-purple-700 dark:text-purple-300",
  },
  automation: {
    bg: "bg-stone-500/8 dark:bg-stone-500/15",
    icon: "text-stone-600 dark:text-stone-400",
    border: "group-hover:border-stone-500/20",
    tag: "bg-stone-500/8 text-stone-700 dark:text-stone-300",
  },
};

const DEFAULT_ACCENT = {
  bg: "bg-secondary",
  icon: "text-foreground",
  border: "group-hover:border-border",
  tag: "bg-secondary text-muted-foreground",
};

interface SkillCardProps {
  skill: SkillMetadata;
  onExecute?: (skillId: string) => void;
  index?: number;
}

export function SkillCard({ skill, onExecute, index = 0 }: SkillCardProps) {
  const t = useTranslations("skills");
  const router = useRouter();
  const Icon =
    CATEGORY_ICONS[skill.category as keyof typeof CATEGORY_ICONS] || Code;
  const accent =
    CATEGORY_ACCENT[skill.category as keyof typeof CATEGORY_ACCENT] || DEFAULT_ACCENT;

  const paramCount = skill.parameters?.length ?? 0;

  return (
    <div
      className={cn(
        "group relative border border-border/50 rounded-xl p-4",
        "hover:border-border hover:shadow-sm",
        "transition-all duration-200",
        "cursor-pointer",
        accent.border,
        "animate-fade-in"
      )}
      style={{ animationDelay: `${index * 40}ms`, animationFillMode: "backwards" }}
      onClick={() => router.push(`/skills/${skill.id}`)}
    >
      {/* Header row: icon + name + version */}
      <div className="flex items-start gap-3">
        <div className={cn("shrink-0 p-2 rounded-lg", accent.bg)}>
          <Icon className={cn("w-4 h-4", accent.icon)} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h4 className="font-semibold text-sm text-foreground truncate">
              {skill.name}
            </h4>
            <span className="shrink-0 text-[10px] text-muted-foreground/60 font-mono">
              v{skill.version}
            </span>
          </div>
          <p className="text-xs text-muted-foreground mt-1 line-clamp-2 leading-relaxed">
            {skill.description}
          </p>
        </div>
      </div>

      {/* Tags */}
      {skill.tags && skill.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-3">
          {skill.tags.slice(0, 4).map((tag) => (
            <span
              key={tag}
              className={cn(
                "inline-flex text-[10px] font-medium px-1.5 py-0.5 rounded",
                accent.tag
              )}
            >
              {tag}
            </span>
          ))}
          {skill.tags.length > 4 && (
            <span className="text-[10px] text-muted-foreground/50 px-1 py-0.5">
              +{skill.tags.length - 4}
            </span>
          )}
        </div>
      )}

      {/* Footer: metadata + action */}
      <div className="flex items-center justify-between mt-3 pt-3 border-t border-border/30">
        <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
          <span className="uppercase tracking-wider font-medium">
            {skill.category}
          </span>
          {paramCount > 0 && (
            <>
              <span className="text-border">|</span>
              <span>{t("parameters", { count: paramCount })}</span>
            </>
          )}
        </div>

        {onExecute && (
          <Button
            size="sm"
            variant="ghost"
            className="h-7 px-2.5 text-xs gap-1 cursor-pointer opacity-0 group-hover:opacity-100 transition-opacity duration-150"
            onClick={(e) => {
              e.stopPropagation();
              onExecute(skill.id);
            }}
          >
            {t("useSkill")}
            <ArrowRight className="w-3 h-3" />
          </Button>
        )}
      </div>
    </div>
  );
}
