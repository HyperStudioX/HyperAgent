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
        "group w-full flex items-center justify-center gap-2 h-10 px-4 text-sm font-medium rounded-xl",
        "bg-gradient-to-r from-foreground to-foreground/90 text-background",
        "hover:from-foreground/90 hover:to-foreground/80",
        "shadow-sm hover:shadow-md transition-all duration-200",
        "active:scale-[0.98]"
      )}
    >
      <Plus className="w-4 h-4 transition-transform duration-300 group-hover:rotate-90" />
      <span>{t("create")}</span>
    </button>
  );
}
