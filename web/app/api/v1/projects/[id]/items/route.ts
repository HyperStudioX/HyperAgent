import { createProxyHandler } from "@/lib/api/proxy";

export const dynamic = "force-dynamic";

const handler = createProxyHandler({
    endpoint: "/api/v1/projects/[id]/items",
});

export { handler as POST, handler as DELETE };
