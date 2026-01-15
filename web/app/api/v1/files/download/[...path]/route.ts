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
        const url = `${API_URL}/api/v1/files/download/${path}`;

        console.log(`[File Download] Request path: ${path}`);

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
    console.log(`[File Download] Downloading: ${path}`);
    console.log(`[File Download] Has session token: ${!!sessionToken}`);
    console.log(`[File Download] Has Authorization header: ${headers.has("Authorization")}`);

    try {
        const response = await fetch(url, {
            method: "GET",
            headers,
            cache: "no-store",
            credentials: "include",
        });

        if (!response.ok) {
            console.error(`[File Download] Error: ${response.status} for ${url}`);
            const errorText = await response.text();
            console.error(`[File Download] Response: ${errorText}`);
            return NextResponse.json(
                { error: response.status === 401 ? "Unauthorized" : "File not found" },
                { status: response.status }
            );
        }

        // Get content type from response
        const contentType = response.headers.get("content-type") || "application/octet-stream";

        // Stream the file back to client
        return new Response(response.body, {
            status: response.status,
            headers: {
                "Content-Type": contentType,
                "Content-Disposition": response.headers.get("content-disposition") || "inline",
            }
        });

    } catch (error) {
        console.error(`[API Proxy] Error downloading file:`, error);
        return NextResponse.json({ error: "Failed to download file" }, { status: 502 });
    }
    } catch (outerError) {
        console.error(`[API Proxy] Unhandled error in file download handler:`, outerError);
        return NextResponse.json({ error: "Internal server error" }, { status: 500 });
    }
}

export { handler as GET };
