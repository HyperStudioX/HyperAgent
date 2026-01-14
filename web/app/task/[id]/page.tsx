import { MainLayout } from "@/components/layout/main-layout";
import { TaskProgress } from "@/components/task/task-progress";

export const dynamic = "force-dynamic";

interface TaskPageProps {
  params: Promise<{ id: string }>;
}

export default async function TaskPage({ params }: TaskPageProps) {
  const { id } = await params;
  return (
    <MainLayout>
      <TaskProgress key={id} taskId={id} />
    </MainLayout>
  );
}
