import { createProxyHandler } from "@/lib/api/proxy";

export const dynamic = "force-dynamic";

const handler = createProxyHandler({
    endpoint: "/api/v1/tasks",
    emptyResponse: { tasks: [], total: 0, limit: 20, offset: 0 },
});

export { handler as GET, handler as POST, handler as DELETE, handler as PUT, handler as PATCH };
