import { createProxyHandler } from "@/lib/api/proxy";

export const dynamic = "force-dynamic";

const handler = createProxyHandler({
    endpoint: "/api/v1/mcp/servers",
    emptyResponse: { servers: [] },
});

export { handler as GET, handler as POST };
