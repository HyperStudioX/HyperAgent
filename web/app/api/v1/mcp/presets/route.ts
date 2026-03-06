import { createProxyHandler } from "@/lib/api/proxy";

export const dynamic = "force-dynamic";

const handler = createProxyHandler({
    endpoint: "/api/v1/mcp/presets",
    emptyResponse: { presets: [] },
});

export { handler as GET };
