import { createProxyHandler } from "@/lib/api/proxy";

export const dynamic = "force-dynamic";

const handler = createProxyHandler({
    endpoint: "/api/v1/sandbox/files",
    emptyResponse: { success: true, entries: [] },
});

export { handler as GET };
