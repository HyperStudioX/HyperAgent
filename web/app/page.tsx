import { MainLayout } from "@/components/layout/main-layout";
import { ChatInterface } from "@/components/query/chat-interface";

export const dynamic = "force-dynamic";

export default function Home() {
  return (
    <MainLayout>
      <ChatInterface />
    </MainLayout>
  );
}
