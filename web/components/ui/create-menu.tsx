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
        "w-full flex items-center justify-center gap-2 h-10 px-4 text-sm font-medium rounded-lg",
        "bg-primary text-primary-foreground",
        "hover:bg-primary/90 transition-colors"
      )}
    >
      <Plus className="w-4 h-4" />
      <span>{t("create")}</span>
    </button>
  );
}
