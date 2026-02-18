
// Use NEXT_PUBLIC_API_URL or fallback to 127.0.0.1
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8765/api";

export async function fetcher<T>(url: string): Promise<T> {
    const res = await fetch(url);
    if (!res.ok) {
        throw new Error("Failed to fetch data");
    }
    return res.json();
}

async function mutate(url: string, method: string, body?: unknown) {
    const res = await fetch(url, {
        method,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Unknown error" }));
        throw new Error(err.detail || `${method} failed`);
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
