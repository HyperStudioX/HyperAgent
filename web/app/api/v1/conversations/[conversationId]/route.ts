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

// GET /api/v1/conversations/[conversationId] - Get conversation with messages
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ conversationId: string }> }
) {
  const { conversationId } = await params;

  try {
    const response = await fetch(
      `${API_URL}/api/v1/conversations/${conversationId}`,
      {
        method: "GET",
        headers: getAuthHeaders(request),
      }
    );

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error("[API] Get conversation error:", error);
    return NextResponse.json(
      { error: "Failed to fetch conversation" },
      { status: 502 }
    );
  }
}

// PATCH /api/v1/conversations/[conversationId] - Update conversation
export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ conversationId: string }> }
) {
  const { conversationId } = await params;

  try {
    const body = await request.json();

    const response = await fetch(
      `${API_URL}/api/v1/conversations/${conversationId}`,
      {
        method: "PATCH",
        headers: getAuthHeaders(request),
        body: JSON.stringify(body),
      }
    );

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error("[API] Update conversation error:", error);
    return NextResponse.json(
      { error: "Failed to update conversation" },
      { status: 502 }
    );
  }
}

// DELETE /api/v1/conversations/[conversationId] - Delete conversation
export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ conversationId: string }> }
) {
  const { conversationId } = await params;

  try {
    const response = await fetch(
      `${API_URL}/api/v1/conversations/${conversationId}`,
      {
        method: "DELETE",
        headers: getAuthHeaders(request),
      }
    );

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error("[API] Delete conversation error:", error);
    return NextResponse.json(
      { error: "Failed to delete conversation" },
      { status: 502 }
    );
  }
}
