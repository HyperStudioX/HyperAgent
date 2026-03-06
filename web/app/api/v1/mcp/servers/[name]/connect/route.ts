import { createProxyHandler } from "@/lib/api/proxy";

export const dynamic = "force-dynamic";

const handler = createProxyHandler({
    endpoint: "/api/v1/mcp/servers/[name]/connect",
});

export { handler as POST };
