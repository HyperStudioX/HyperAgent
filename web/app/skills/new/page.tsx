"use client";

import { MainLayout } from "@/components/layout/main-layout";
import { CreateSkillForm } from "@/components/skills/create-skill-form";

export default function CreateSkillPage() {
  return (
    <MainLayout>
      <div className="flex-1 overflow-y-auto">
        <div className="container mx-auto px-6 py-8 max-w-6xl">
          <CreateSkillForm />
        </div>
      </div>
    </MainLayout>
  );
}
