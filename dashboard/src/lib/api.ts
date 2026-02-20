
// Use NEXT_PUBLIC_API_URL or fallback to 127.0.0.1
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8765/api";

function getAuthHeader(): Record<string, string> {
    if (typeof document === "undefined") return {};
    const match = document.cookie.match(/(?:^|; )superactive_auth=([^;]*)/);
    return match ? { Authorization: `Bearer ${match[1]}` } : {};
}

export async function fetcher<T>(url: string): Promise<T> {
    const res = await fetch(url, { headers: { ...getAuthHeader() } });
    if (!res.ok) {
        throw new Error("Failed to fetch data");
    }
    return res.json();
}

async function mutate(url: string, method: string, body?: unknown) {
    const headers: Record<string, string> = { ...getAuthHeader() };
    if (body) {
        headers["Content-Type"] = "application/json";
    }

    const res = await fetch(url, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) {
        let errMessage = `${method} failed`;
        try {
            const err = await res.json();
            if (err.detail) {
                // FastAPI 422 validation errors are arrays
                if (Array.isArray(err.detail)) {
                    errMessage = err.detail.map((e: any) => `${e.loc.join('.')}: ${e.msg}`).join(', ');
                } else {
                    errMessage = String(err.detail);
                }
            }
        } catch (e) {
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
        headers: { ...getAuthHeader() },
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
}) {
    return mutate(`${API_BASE_URL}/settings`, "PUT", data);
}
