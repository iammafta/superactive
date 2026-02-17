
// Use NEXT_PUBLIC_API_URL or fallback to 127.0.0.1
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8765/api";

export async function fetcher<T>(url: string): Promise<T> {
    const res = await fetch(url);
    if (!res.ok) {
        throw new Error("Failed to fetch data");
    }
    return res.json();
}

export async function triggerCall(to: string, agentId: string) {
    const res = await fetch(`${API_BASE_URL}/outbound-call`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ to, agent_id: agentId }),
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Unknown error" }));
        throw new Error(err.detail || "Call failed");
    }
    return res.json();
}
