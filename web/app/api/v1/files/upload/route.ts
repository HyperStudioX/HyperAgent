import { NextRequest, NextResponse } from "next/server";

const API_URL = (
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080"
).replace("localhost", "127.0.0.1");

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const url = `${API_URL}/api/v1/files/upload`;

  // Get session token
  const sessionToken =
    request.cookies.get("next-auth.session-token")?.value ||
    request.cookies.get("__Secure-next-auth.session-token")?.value;

  if (!sessionToken) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    // Forward the multipart form data
    const formData = await request.formData();

    const response = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${sessionToken}`,
      },
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      return NextResponse.json(error, { status: response.status });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("[API Proxy] File upload error:", error);
    return NextResponse.json({ error: "Upload failed" }, { status: 500 });
  }
}
