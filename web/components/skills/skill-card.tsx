"use client";

import { SkillMetadata } from "@/lib/types/skills";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Code, Sparkles, Search, BarChart3, FileText } from "lucide-react";

const CATEGORY_ICONS = {
  research: Search,
  code: Code,
  data: BarChart3,
  creative: Sparkles,
  automation: FileText,
};

const CATEGORY_COLORS = {
  research: "bg-secondary text-foreground",
  code: "bg-secondary text-foreground",
  data: "bg-secondary text-foreground",
  creative: "bg-secondary text-foreground",
  automation: "bg-secondary text-foreground",
};

interface SkillCardProps {
  skill: SkillMetadata;
  onExecute?: (skillId: string) => void;
}

export function SkillCard({ skill, onExecute }: SkillCardProps) {
  const Icon = CATEGORY_ICONS[skill.category as keyof typeof CATEGORY_ICONS] || Code;
  const colorClass = CATEGORY_COLORS[skill.category as keyof typeof CATEGORY_COLORS] || "bg-secondary text-foreground";

  return (
    <Card className="p-4 hover:border-border transition-colors">
      <div className="flex items-start gap-3">
        <div className={`p-2 rounded-lg ${colorClass}`}>
          <Icon className="w-4 h-4" />
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="font-semibold text-sm">{skill.name}</h4>
          <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
            {skill.description}
          </p>

          {skill.tags && skill.tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-3">
              {skill.tags.map((tag) => (
                <Badge
                  key={tag}
                  variant="secondary"
                  className="text-xs px-2 py-0.5"
                >
                  {tag}
                </Badge>
              ))}
            </div>
          )}

          <div className="flex items-center gap-2 mt-3">
            <Badge variant="outline" className="text-xs">
              {skill.category}
            </Badge>
            <span className="text-xs text-muted-foreground">
              v{skill.version}
            </span>
          </div>

          {onExecute && (
            <Button
              size="sm"
              variant="outline"
              className="w-full mt-3"
              onClick={() => onExecute(skill.id)}
            >
              Use Skill
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}
