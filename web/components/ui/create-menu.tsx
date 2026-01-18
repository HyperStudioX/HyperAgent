"use client";

import React from "react";
import { useTranslations } from "next-intl";
import { Plus } from "lucide-react";
import { cn } from "@/lib/utils";

interface CreateMenuProps {
  onCreate: () => void;
}

export function CreateMenu({ onCreate }: CreateMenuProps) {
  const t = useTranslations("sidebar");

  return (
    <button
      onClick={onCreate}
      className={cn(
        "group w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium text-left transition-colors",
        "text-foreground hover:bg-secondary/50"
      )}
      aria-label={t("create")}
    >
      <div className="flex-shrink-0 w-7 h-7 rounded-md flex items-center justify-center bg-secondary group-hover:bg-secondary transition-colors">
        <Plus className="w-4 h-4 text-muted-foreground group-hover:text-foreground group-hover:rotate-90 transition-all" />
      </div>
      <span className="flex-1">{t("create")}</span>
    </button>
  );
}
