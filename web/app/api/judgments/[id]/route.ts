import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://localhost:8000";
const BACKEND_TIMEOUT_MS = 10_000;

export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), BACKEND_TIMEOUT_MS);

  try {
    const backendResponse = await fetch(`${API_BASE_URL}/judgments/${encodeURIComponent(id)}`, {
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
