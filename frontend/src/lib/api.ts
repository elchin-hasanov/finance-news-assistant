import type { AnalyzeInput, AnalyzeResponse, ApiErrorEnvelope } from "@/lib/schemas";

const baseUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export type ApiError = Error & {
  code?: string;
  hint?: string | null;
  status?: number;
  payload?: unknown;
};

export async function analyze(input: AnalyzeInput): Promise<AnalyzeResponse> {
  const res = await fetch(`${baseUrl}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      url: input.url ? input.url : null,
      text: input.text ? input.text : null,
    }),
  });

  const json = (await res.json().catch(() => null)) as AnalyzeResponse | ApiErrorEnvelope | null;

  if (!res.ok) {
    const err = (json as ApiErrorEnvelope | null)?.error;
    const message = err?.message || `Request failed (${res.status})`;
    const hint = err?.hint;
    const code = err?.code || "UNKNOWN";
  const e: ApiError = new Error(message);
  e.code = code;
  e.hint = hint;
  e.status = res.status;
  e.payload = json;
  throw e;
  }

  return json as AnalyzeResponse;
}
