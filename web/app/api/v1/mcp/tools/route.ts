import { createProxyHandler } from "@/lib/api/proxy";

export const dynamic = "force-dynamic";

const handler = createProxyHandler({
    endpoint: "/api/v1/mcp/tools",
    emptyResponse: { tools: [], count: 0 },
});

export { handler as GET };
