import { NextRequest, NextResponse } from "next/server";

const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080").replace("localhost", "127.0.0.1");

export const dynamic = "force-dynamic";

async function handler(
    request: NextRequest
) {
    const { searchParams } = new URL(request.url);
    const queryString = searchParams.toString();
    const url = `${API_URL}/api/v1/conversations${queryString ? `?${queryString}` : ""}`;

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

        // Support streaming for SSE (/stream endpoints)
        if (response.headers.get("content-type")?.includes("text/event-stream")) {
            return new Response(response.body, {
                status: response.status,
                headers: responseHeaders
            });
        }

        // Get response body text first to check if it's empty
        const responseText = await response.text();
        
        // For regular JSON or other responses
        const contentType = response.headers.get("content-type");
        if (contentType?.includes("application/json")) {
            try {
                // Handle empty response body
                if (!responseText || responseText.trim() === "") {
                    // Return empty array for list endpoints
                    if (response.status === 200) {
                        return NextResponse.json([], { 
                            status: response.status, 
                            headers: responseHeaders 
                        });
                    }
                    return NextResponse.json({ error: "Empty response" }, { 
                        status: response.status || 500, 
                        headers: responseHeaders 
                    });
                }
                const data = JSON.parse(responseText);
                return NextResponse.json(data, { status: response.status, headers: responseHeaders });
            } catch (parseError) {
                console.error(`[API Proxy] JSON parse error for ${url}:`, parseError);
                return NextResponse.json(
                    { error: "Invalid JSON response", detail: responseText.substring(0, 200) },
                    { status: response.status || 500, headers: responseHeaders }
                );
            }
        }

        // For non-JSON responses, return as-is
        return new Response(responseText || response.body, {
            status: response.status,
            headers: responseHeaders
        });

    } catch (error) {
        console.error(`[API Proxy] Error for ${url}:`, error);
        const errorMessage = error instanceof Error ? error.message : String(error);
        return NextResponse.json(
            { error: "Backend error", detail: errorMessage },
            { status: 502 }
        );
    }
}

export { handler as GET, handler as POST, handler as DELETE, handler as PUT, handler as PATCH };
