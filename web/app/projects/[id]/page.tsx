"use client";

import { use } from "react";
import { MainLayout } from "@/components/layout/main-layout";
import { ProjectDetailView } from "@/components/projects";

export default function ProjectDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);

  return (
    <MainLayout>
      <div className="flex-1 overflow-y-auto">
        <div className="container mx-auto px-6 py-8 max-w-6xl">
          <ProjectDetailView projectId={id} />
        </div>
      </div>
    </MainLayout>
  );
}
