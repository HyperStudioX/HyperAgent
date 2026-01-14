import { MainLayout } from "@/components/layout/main-layout";
import { UnifiedInterface } from "@/components/query/unified-interface";

export const dynamic = "force-dynamic";

export default function Home() {
  return (
    <MainLayout>
      <UnifiedInterface />
    </MainLayout>
  );
}
