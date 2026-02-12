import { createProxyHandler } from "@/lib/api/proxy";

export const dynamic = "force-dynamic";

const handler = createProxyHandler({
    endpoint: "/api/v1/sandbox/files/content",
    emptyResponse: { success: false, content: "" },
});

export { handler as GET };
