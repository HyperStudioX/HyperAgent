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

// GET /api/v1/tasks - List tasks
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const queryString = searchParams.toString();
    const url = `${API_URL}/api/v1/tasks${queryString ? `?${queryString}` : ""}`;

    const response = await fetch(url, {
      method: "GET",
      headers: getAuthHeaders(request),
    });

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error("[API] List tasks error:", error);
    return NextResponse.json(
      { error: "Failed to fetch tasks" },
      { status: 502 }
    );
  }
}
