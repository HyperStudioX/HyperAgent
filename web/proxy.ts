import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Simple middleware that just passes through
// Locale detection is handled by i18n/request.ts via cookies
export function proxy(request: NextRequest) {
  return NextResponse.next();
}

export const config = {
  // Match all pathnames except API routes, static files, etc.
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
};
