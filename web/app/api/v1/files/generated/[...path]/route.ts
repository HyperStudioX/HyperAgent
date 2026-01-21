import { NextRequest, NextResponse } from "next/server";

const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080").replace("localhost", "127.0.0.1");

export const dynamic = "force-dynamic";

async function handler(
    request: NextRequest,
    { params }: { params: Promise<{ path: string[] }> }
) {
    try {
        const { path: pathArray } = await params;
        const path = pathArray.join("/");
        const url = `${API_URL}/api/v1/files/generated/${path}`;

        console.log(`[Generated File] Request path: ${path}`);

        // Forward headers
        const headers = new Headers();
        request.headers.forEach((value, key) => {
            // Avoid forwarding restricted headers
            if (key.toLowerCase() !== 'host' && key.toLowerCase() !== 'connection') {
                headers.set(key, value);
            }
        });

        // Forward cookies to backend
        const cookieHeader = request.headers.get("cookie");
        if (cookieHeader) {
            headers.set("Cookie", cookieHeader);
        }

        // Ensure NextAuth session is converted to Bearer token for the backend
        const sessionToken =
            request.cookies.get("next-auth.session-token")?.value ||
            request.cookies.get("__Secure-next-auth.session-token")?.value;

        if (sessionToken && !headers.has("Authorization")) {
            headers.set("Authorization", `Bearer ${sessionToken}`);
        }

        // Debug logging
        console.log(`[Generated File] Downloading: ${path}`);
        console.log(`[Generated File] Has session token: ${!!sessionToken}`);

        try {
            const response = await fetch(url, {
                method: "GET",
                headers,
                cache: "no-store",
                credentials: "include",
            });

            if (!response.ok) {
                console.error(`[Generated File] Error: ${response.status} for ${url}`);
                const errorText = await response.text();
                console.error(`[Generated File] Response: ${errorText}`);
                return NextResponse.json(
                    { error: response.status === 401 ? "Unauthorized" : "File not found" },
                    { status: response.status }
                );
            }

            // Get content type from response
            const contentType = response.headers.get("content-type") || "image/png";

            // Stream the file back to client with caching headers
            return new Response(response.body, {
                status: response.status,
                headers: {
                    "Content-Type": contentType,
                    "Content-Disposition": response.headers.get("content-disposition") || "inline",
                    "Cache-Control": response.headers.get("cache-control") || "public, max-age=31536000",
                }
            });

        } catch (error) {
            console.error(`[Generated File] Error downloading file:`, error);
            return NextResponse.json({ error: "Failed to download generated file" }, { status: 502 });
        }
    } catch (outerError) {
        console.error(`[Generated File] Unhandled error in handler:`, outerError);
        return NextResponse.json({ error: "Internal server error" }, { status: 500 });
    }
}

export { handler as GET };
