import { NextRequest } from "next/server";

export const runtime = "nodejs";

export async function POST(request: NextRequest) {
  // Use 127.0.0.1 to bypass proxy
  const apiUrl = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080").replace("localhost", "127.0.0.1");

  // Get NextAuth session token from cookies
  const sessionToken =
    request.cookies.get("next-auth.session-token")?.value ||
    request.cookies.get("__Secure-next-auth.session-token")?.value;

  try {
    const body = await request.json();

    const headers: HeadersInit = {
      "Content-Type": "application/json",
    };

    // Forward NextAuth JWT to backend
    if (sessionToken) {
      headers["Authorization"] = `Bearer ${sessionToken}`;
    }

    const response = await fetch(`${apiUrl}/api/v1/query/stream`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      return new Response(
        JSON.stringify({ error: `Backend error: ${response.status}` }),
        { status: response.status, headers: { "Content-Type": "application/json" } }
      );
    }

    if (!response.body) {
      return new Response(
        JSON.stringify({ error: "No response body from backend" }),
        { status: 500, headers: { "Content-Type": "application/json" } }
      );
    }

    // Stream the response directly to the client
    return new Response(response.body, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
      },
    });
  } catch (error) {
    console.error("Stream proxy error:", error);
    return new Response(
      JSON.stringify({ error: "Failed to connect to backend" }),
      { status: 502, headers: { "Content-Type": "application/json" } }
    );
  }
}
