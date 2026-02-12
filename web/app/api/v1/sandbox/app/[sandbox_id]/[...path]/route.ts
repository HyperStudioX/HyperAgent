import { createProxyHandler } from "@/lib/api/proxy";

export const dynamic = "force-dynamic";

const handler = createProxyHandler({
    endpoint: "/api/v1/sandbox/app/[sandbox_id]/[...path]",
    timeout: 30000,
});

export { handler as GET, handler as POST, handler as PUT, handler as DELETE };
