import { NextRequest, NextResponse } from "next/server";

/**
 * Server-side proxy to the FastAPI backend's POST /search. Kept as a proxy
 * (rather than the browser calling the backend directly) for two reasons:
 * it keeps API_BASE_URL out of the client bundle (no NEXT_PUBLIC_ prefix
 * needed), and it avoids needing CORS configured on the backend at all,
 * since the browser only ever talks to this same-origin route.
 */

const API_BASE_URL = process.env.API_BASE_URL ?? "http://localhost:8000";
const BACKEND_TIMEOUT_MS = 10_000;

export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid JSON body." }, { status: 400 });
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), BACKEND_TIMEOUT_MS);

  try {
    const backendResponse = await fetch(`${API_BASE_URL}/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    const data = await backendResponse.json().catch(() => null);
    return NextResponse.json(data, { status: backendResponse.status });
  } catch (err) {
    const timedOut = err instanceof DOMException && err.name === "AbortError";
    return NextResponse.json(
      { detail: timedOut ? "Backend request timed out." : "Could not reach the search backend." },
      { status: 502 }
    );
  } finally {
    clearTimeout(timeoutId);
  }
}
