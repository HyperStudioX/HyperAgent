import { NextRequest, NextResponse } from "next/server";

const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080").replace("localhost", "127.0.0.1");

export const dynamic = "force-dynamic";

async function handler(
    request: NextRequest
) {
    const { searchParams } = new URL(request.url);
    const queryString = searchParams.toString();
    const url = `${API_URL}/api/v1/query${queryString ? `?${queryString}` : ""}`;

    // Forward headers
    const headers = new Headers();
    request.headers.forEach((value, key) => {
        // Avoid forwarding restricted headers
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

    const method = request.method;
    const hasBody = !["GET", "HEAD"].includes(method);

    try {
        const fetchOptions: RequestInit = {
            method,
            headers,
            cache: "no-store",
        };

        if (hasBody) {
            // Clone the request body to avoid detached ArrayBuffer issues
            const bodyText = await request.text();
            fetchOptions.body = bodyText;
        }

        const response = await fetch(url, fetchOptions);

        // Filter response headers to avoid issues with Next.js
        const responseHeaders = new Headers();
        response.headers.forEach((value, key) => {
            if (key.toLowerCase() !== 'content-encoding' && key.toLowerCase() !== 'transfer-encoding') {
                responseHeaders.set(key, value);
            }
        });

        // For regular JSON or other responses
        const contentType = response.headers.get("content-type");
        if (contentType?.includes("application/json")) {
            const data = await response.json();
            return NextResponse.json(data, { status: response.status, headers: responseHeaders });
        }

        return new Response(response.body, {
            status: response.status,
            headers: responseHeaders
        });

    } catch (error) {
        console.error(`[API Proxy] Error for ${url}:`, error);
        return NextResponse.json({ error: "Backend error" }, { status: 502 });
    }
}

export { handler as GET, handler as POST, handler as DELETE, handler as PUT, handler as PATCH };
