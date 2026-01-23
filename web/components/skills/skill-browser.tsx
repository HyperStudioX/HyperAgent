"use client";

import { useEffect, useState } from "react";
import { listSkills } from "@/lib/api/skills";
import { SkillMetadata } from "@/lib/types/skills";
import { SkillCard } from "./skill-card";
import { Input } from "@/components/ui/input";
import { Search, Loader2 } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface SkillBrowserProps {
  onSkillSelect?: (skillId: string) => void;
}

export function SkillBrowser({ onSkillSelect }: SkillBrowserProps) {
  const [skills, setSkills] = useState<SkillMetadata[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");

  useEffect(() => {
    loadSkills();
  }, []);

  async function loadSkills() {
    try {
      setLoading(true);
      const data = await listSkills();
      setSkills(data);
    } catch (error) {
      console.error("Failed to load skills:", error);
    } finally {
      setLoading(false);
    }
  }

  // Get unique categories
  const categories = Array.from(new Set(skills.map((s) => s.category)));

  // Filter skills
  const filteredSkills = skills.filter((skill) => {
    const matchesSearch =
      searchQuery === "" ||
      skill.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      skill.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      skill.tags?.some((tag) =>
        tag.toLowerCase().includes(searchQuery.toLowerCase())
      );

    const matchesCategory =
      categoryFilter === "all" || skill.category === categoryFilter;

    return matchesSearch && matchesCategory;
  });

  // Group by category
  const groupedSkills = categories.reduce((acc, category) => {
    acc[category] = filteredSkills.filter((s) => s.category === category);
    return acc;
  }, {} as Record<string, SkillMetadata[]>);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="Search skills..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>
          <Select value={categoryFilter} onValueChange={setCategoryFilter}>
            <SelectTrigger className="w-full sm:w-[180px]">
              <SelectValue placeholder="All Categories" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Categories</SelectItem>
              {categories.map((category) => (
                <SelectItem key={category} value={category}>
                  <span className="capitalize">{category}</span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="text-sm text-muted-foreground">
          {filteredSkills.length} {filteredSkills.length === 1 ? "skill" : "skills"} available
        </div>
      </div>

      {filteredSkills.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          No skills found matching your criteria.
        </div>
      ) : (
        <div className="space-y-6">
          {categories.map((category) => {
            const categorySkills = groupedSkills[category];
            if (!categorySkills || categorySkills.length === 0) return null;

            return (
              <div key={category}>
                <h3 className="text-lg font-medium capitalize mb-3">
                  {category}
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {categorySkills.map((skill) => (
                    <SkillCard
                      key={skill.id}
                      skill={skill}
                      onExecute={onSkillSelect}
                    />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
