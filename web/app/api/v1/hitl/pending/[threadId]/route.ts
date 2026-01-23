import { NextRequest, NextResponse } from "next/server";

const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080").replace("localhost", "127.0.0.1");

export const dynamic = "force-dynamic";

async function handler(
    request: NextRequest,
    { params }: { params: Promise<{ threadId: string }> }
) {
    const { threadId } = await params;
    const url = `${API_URL}/api/v1/hitl/pending/${threadId}`;

    // Forward headers
    const headers = new Headers();
    request.headers.forEach((value, key) => {
        if (key.toLowerCase() !== 'host' && key.toLowerCase() !== 'connection') {
            headers.set(key, value);
        }
    });

    // Ensure NextAuth session is converted to Bearer token for the backend
    const sessionToken =
        request.cookies.get("next-auth.session-token")?.value ||
        request.cookies.get("__Secure-next-auth.session-token")?.value;

    if (sessionToken && !headers.has("Authorization")) {
        headers.set("Authorization", `Bearer ${sessionToken}`);
    }

    try {
        const response = await fetch(url, {
            method: "GET",
            headers,
            cache: "no-store",
        });

        const data = await response.json();
        return NextResponse.json(data, { status: response.status });

    } catch (error) {
        console.error(`[HITL API Proxy] Error for ${url}:`, error);
        return NextResponse.json({ error: "Backend error" }, { status: 502 });
    }
}

export { handler as GET };
