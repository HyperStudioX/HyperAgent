"use client";

import { use } from "react";
import { MainLayout } from "@/components/layout/main-layout";
import { SkillDetailView } from "@/components/skills/skill-detail-view";

export default function SkillDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);

  return (
    <MainLayout>
      <div className="flex-1 overflow-y-auto">
        <div className="container mx-auto px-6 py-8 max-w-6xl">
          <SkillDetailView skillId={id} />
        </div>
      </div>
    </MainLayout>
  );
}
