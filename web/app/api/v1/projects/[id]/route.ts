import { createProxyHandler } from "@/lib/api/proxy";

export const dynamic = "force-dynamic";

const handler = createProxyHandler({
    endpoint: "/api/v1/projects/[id]",
});

export { handler as GET, handler as PATCH, handler as DELETE };
