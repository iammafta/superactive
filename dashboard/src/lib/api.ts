
// Use NEXT_PUBLIC_API_URL or fallback to localhost
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8765/api";


export async function fetcher<T>(url: string): Promise<T> {
    const res = await fetch(url, { credentials: "include" });
    if (!res.ok) {
        throw new Error("Failed to fetch data");
    }
    return res.json();
}

// ── Auth ──────────────────────────────────────────────────────────

export async function getWsTicket(): Promise<string | null> {
    try {
        const res = await fetch(`${API_BASE_URL}/auth/ticket`, {
            method: "POST",
            credentials: "include",
        });
        if (!res.ok) return null;
        const data = await res.json();
        return data.ticket || null;
    } catch {
        return null;
    }
}

async function mutate(url: string, method: string, body?: unknown) {
    const headers: Record<string, string> = {};
    if (body) {
        headers["Content-Type"] = "application/json";
    }

    const res = await fetch(url, {
        method,
        headers,
        credentials: "include",
        body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) {
        let errMessage = `${method} failed`;
        try {
            const err = await res.json();
            if (err.detail) {
                // FastAPI 422 validation errors are arrays
                if (Array.isArray(err.detail)) {
                    errMessage = err.detail.map((e: { loc: string[]; msg: string }) => `${e.loc.join('.')}: ${e.msg}`).join(', ');
                } else {
                    errMessage = String(err.detail);
                }
            }
        } catch {
            // keep standard failure
        }
        throw new Error(errMessage);
    }
    return res.json();
}

// ── Outbound Calls ────────────────────────────────────────────────

export async function triggerCall(to: string, agentId: string) {
    return mutate(`${API_BASE_URL}/outbound-call`, "POST", { to, agent_id: agentId });
}

// ── Agent CRUD ────────────────────────────────────────────────────

export async function createAgent(data: Record<string, unknown>) {
    return mutate(`${API_BASE_URL}/agents`, "POST", data);
}

export async function updateAgent(agentId: string, data: Record<string, unknown>) {
    return mutate(`${API_BASE_URL}/agents/${agentId}`, "PUT", data);
}

export async function deleteAgent(agentId: string) {
    return mutate(`${API_BASE_URL}/agents/${agentId}`, "DELETE");
}

// ── Campaign CRUD ─────────────────────────────────────────────────

export async function createCampaign(data: Record<string, unknown>) {
    return mutate(`${API_BASE_URL}/campaigns`, "POST", data);
}

export async function updateCampaign(id: string, data: Record<string, unknown>) {
    return mutate(`${API_BASE_URL}/campaigns/${id}`, "PUT", data);
}

export async function deleteCampaign(id: string) {
    return mutate(`${API_BASE_URL}/campaigns/${id}`, "DELETE");
}

export async function uploadContacts(campaignId: string, csvFile: File) {
    const formData = new FormData();
    formData.append("file", csvFile);
    const res = await fetch(`${API_BASE_URL}/campaigns/${campaignId}/upload-contacts`, {
        method: "POST",
        credentials: "include",
        body: formData,
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Upload failed" }));
        throw new Error(err.detail || "Failed to upload contacts");
    }
    return res.json();
}

export async function startCampaign(id: string) {
    return mutate(`${API_BASE_URL}/campaigns/${id}/start`, "POST");
}

export async function pauseCampaign(id: string) {
    return mutate(`${API_BASE_URL}/campaigns/${id}/pause`, "POST");
}

export async function resumeCampaign(id: string) {
    return mutate(`${API_BASE_URL}/campaigns/${id}/resume`, "POST");
}

export async function resetCampaign(id: string) {
    return mutate(`${API_BASE_URL}/campaigns/${id}/reset`, "POST");
}

// ── Analytics ────────────────────────────────────────────────────

export async function deleteHistory() {
    return mutate(`${API_BASE_URL}/analytics/history`, "DELETE");
}

// ── Settings ─────────────────────────────────────────────────────

export async function saveSettings(data: {
    business_name?: string;
    owner_email?: string;
    public_url?: string;
    twilio_sid?: string;
    twilio_token?: string;
    twilio_phone?: string;
}) {
    return mutate(`${API_BASE_URL}/settings`, "PUT", data);
}
