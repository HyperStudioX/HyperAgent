import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

function getAuthHeaders(request: NextRequest): HeadersInit {
  const sessionToken =
    request.cookies.get("next-auth.session-token")?.value ||
    request.cookies.get("__Secure-next-auth.session-token")?.value;

  const headers: HeadersInit = {
    "Content-Type": "application/json",
  };

  if (sessionToken) {
    headers["Authorization"] = `Bearer ${sessionToken}`;
  }

  return headers;
}

// GET /api/v1/conversations - List conversations
export async function GET(request: NextRequest) {
  try {
    const response = await fetch(`${API_URL}/api/v1/conversations`, {
      method: "GET",
      headers: getAuthHeaders(request),
    });

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error("[API] List conversations error:", error);
    return NextResponse.json(
      { error: "Failed to fetch conversations" },
      { status: 502 }
    );
  }
}

// POST /api/v1/conversations - Create conversation
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    const response = await fetch(`${API_URL}/api/v1/conversations`, {
      method: "POST",
      headers: getAuthHeaders(request),
      body: JSON.stringify(body),
    });

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error("[API] Create conversation error:", error);
    return NextResponse.json(
      { error: "Failed to create conversation" },
      { status: 502 }
    );
  }
}
