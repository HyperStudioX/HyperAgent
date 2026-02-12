import { MainLayout } from "@/components/layout/main-layout";
import { ResearchProgress } from "@/components/task/research-progress";

interface TaskPageProps {
  params: Promise<{ id: string }>;
}

export default async function TaskPage({ params }: TaskPageProps) {
  const { id } = await params;
  return (
    <MainLayout>
      <ResearchProgress key={id} taskId={id} />
    </MainLayout>
  );
}
