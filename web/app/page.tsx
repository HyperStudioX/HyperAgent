import { MainLayout } from "@/components/layout/main-layout";
import { ChatInterface } from "@/components/query/chat-interface";

export default function Home() {
  return (
    <MainLayout>
      <ChatInterface />
    </MainLayout>
  );
}
