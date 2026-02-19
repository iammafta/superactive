"use client";

import { useState, useRef } from "react";
import useSWR from "swr";
import {
    API_BASE_URL, fetcher,
    createCampaign, uploadContacts,
    startCampaign, pauseCampaign, resumeCampaign, deleteCampaign, resetCampaign
} from "@/lib/api";
import type { CampaignConfig } from "@/lib/types";

type Campaign = CampaignConfig;

interface Agent {
    id: string;
    name: string;
    description?: string;
}

const STATUS_BADGE: Record<string, string> = {
    active: "badge-success",
    completed: "badge-info",
    paused: "badge-warning",
    draft: "badge-danger",
};

export default function CampaignsPage() {
    // 1. Fetch campaigns and agents
    const { data: campaigns, error: campaignsError, mutate: mutateCampaigns } = useSWR<Campaign[]>(`${API_BASE_URL}/campaigns`, fetcher, { refreshInterval: 3000 });
    const { data: agents } = useSWR<Agent[]>(`${API_BASE_URL}/agents`, fetcher);

    // 2. Local state for modal
    const [showNewCampaign, setShowNewCampaign] = useState(false);
    const [isCreating, setIsCreating] = useState(false);

    // Form state
    const [newCampaignName, setNewCampaignName] = useState("");
    const [selectedAgentId, setSelectedAgentId] = useState("");
    const [contactFile, setContactFile] = useState<File | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // 3. Handlers
    const handleCreate = async () => {
        if (!newCampaignName || !selectedAgentId || !contactFile) {
            alert("Please fill in all fields and upload a CSV file.");
            return;
        }

        try {
            setIsCreating(true);

            // A. Create campaign
            const campaignId = `cam-${Date.now()}`; // Simple ID gen, or let backend handle it if improved
            // Actually backend expects us to provide ID or it creates one? 
            // Looking at server.py: api_create_campaign expects CampaignModel which has id. 
            // Let's generate a clean slug-like ID.
            const cleanId = newCampaignName.toLowerCase().replace(/[^a-z0-9]/g, "-") + "-" + Math.floor(Math.random() * 1000);

            await createCampaign({
                id: cleanId,
                name: newCampaignName,
                agent_id: selectedAgentId,
                status: "draft",
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
                contacts: [], // populated via upload
            });

            // B. Upload contacts
            await uploadContacts(cleanId, contactFile);

            // C. Cleanup
            setShowNewCampaign(false);
            setNewCampaignName("");
            setSelectedAgentId("");
            setContactFile(null);
            mutateCampaigns(); // Refresh list
        } catch (err: any) {
            alert(`Failed to create campaign: ${err.message}`);
        } finally {
            setIsCreating(false);
        }
    };

    const handleStart = async (id: string, e: React.MouseEvent) => {
        e.stopPropagation();
        try { await startCampaign(id); mutateCampaigns(); } catch (err) { console.error(err); }
    };

    const handlePause = async (id: string, e: React.MouseEvent) => {
        e.stopPropagation();
        try { await pauseCampaign(id); mutateCampaigns(); } catch (err) { console.error(err); }
    };

    const handleResume = async (id: string, e: React.MouseEvent) => {
        e.stopPropagation();
        try { await resumeCampaign(id); mutateCampaigns(); } catch (err) { console.error(err); }
    };

    const handleDelete = async (id: string, e: React.MouseEvent) => {
        e.stopPropagation();
        if (!confirm("Are you sure you want to delete this campaign?")) return;
        try { await deleteCampaign(id); mutateCampaigns(); } catch (err) { console.error(err); }
    };

    const handleReset = async (id: string, e: React.MouseEvent) => {
        e.stopPropagation();
        try { await resetCampaign(id); mutateCampaigns(); } catch (err) { console.error(err); }
    };

    const isLoading = !campaigns && !campaignsError;

    return (
        <div>
            {/* Header */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 28 }}>
                <div>
                    <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>Campaigns</h1>
                    <p style={{ fontSize: 14, color: "var(--text-muted)" }}>
                        Outbound calling campaigns — your AI makes the calls
                    </p>
                </div>
                <button className="btn-primary" onClick={() => setShowNewCampaign(true)} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 18 }}>+</span> New Campaign
                </button>
            </div>

            {/* Loading / Error States */}
            {isLoading && <div style={{ padding: 20, color: "var(--text-muted)" }}>Loading campaigns...</div>}
            {campaignsError && <div style={{ padding: 20, color: "red" }}>Failed to load campaigns. Is the backend running?</div>}

            {/* Campaign Cards */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))", gap: 16 }}>
                {campaigns?.map((campaign) => {
                    const pct = campaign.total_contacts > 0
                        ? Math.round((campaign.called / campaign.total_contacts) * 100)
                        : 0;
                    const convRate = campaign.called > 0
                        ? Math.round((campaign.booked / campaign.called) * 100)
                        : 0;

                    return (
                        <div key={campaign.id} className="glass-card" style={{ padding: 24, position: "relative" }}>
                            {/* Delete button (top right) */}
                            <button
                                onClick={(e) => handleDelete(campaign.id, e)}
                                style={{
                                    position: "absolute", top: 16, right: 16,
                                    background: "none", border: "none", cursor: "pointer",
                                    color: "var(--text-muted)", fontSize: 16
                                }}
                                title="Delete Campaign"
                            >
                                🗑️
                            </button>

                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16, paddingRight: 24 }}>
                                <div>
                                    <div style={{ fontSize: 16, fontWeight: 600, color: "var(--text-primary)", marginBottom: 4 }}>
                                        {campaign.name}
                                    </div>
                                    <div style={{ fontSize: 12, color: "var(--text-muted)", textTransform: "capitalize" }}>
                                        Agent: {agents?.find(a => a.id === campaign.agent_id)?.name || campaign.agent_id}
                                    </div>
                                </div>
                                <span className={`badge ${STATUS_BADGE[campaign.status] || "badge-danger"}`}>
                                    {campaign.status}
                                </span>
                            </div>

                            {/* Progress bar */}
                            <div style={{ marginBottom: 16 }}>
                                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                                    <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Progress</span>
                                    <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-primary)" }}>
                                        {campaign.called} / {campaign.total_contacts} ({pct}%)
                                    </span>
                                </div>
                                <div style={{ height: 6, background: "rgba(55, 65, 81, 0.5)", borderRadius: 3, overflow: "hidden" }}>
                                    <div style={{ width: `${pct}%`, height: "100%", borderRadius: 3, background: "linear-gradient(to right, #3b82f6, #8b5cf6)" }} />
                                </div>
                            </div>

                            {/* Stats */}
                            <div style={{ display: "flex", gap: 20, marginBottom: 20 }}>
                                <div>
                                    <div style={{ fontSize: 20, fontWeight: 700, color: "var(--text-primary)" }}>{campaign.booked}</div>
                                    <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Booked</div>
                                </div>
                                <div>
                                    <div style={{ fontSize: 20, fontWeight: 700, color: "var(--text-primary)" }}>{convRate}%</div>
                                    <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Conversion</div>
                                </div>
                                <div>
                                    <div style={{ fontSize: 20, fontWeight: 700, color: "var(--text-primary)" }}>{campaign.failed}</div>
                                    <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Failed</div>
                                </div>
                            </div>

                            {/* Action Buttons */}
                            <div style={{ display: "flex", gap: 8 }}>
                                {campaign.status === "draft" && (
                                    <button className="btn-primary" style={{ flex: 1, padding: "8px 0" }} onClick={(e) => handleStart(campaign.id, e)}>
                                        ▶ Start Campaign
                                    </button>
                                )}
                                {campaign.status === "active" && (
                                    <button className="btn-secondary" style={{ flex: 1, padding: "8px 0", background: "#f59e0b", color: "white", border: "none" }} onClick={(e) => handlePause(campaign.id, e)}>
                                        ⏸ Pause
                                    </button>
                                )}
                                {campaign.status === "paused" && (
                                    <button className="btn-primary" style={{ flex: 1, padding: "8px 0" }} onClick={(e) => handleResume(campaign.id, e)}>
                                        ▶ Resume
                                    </button>
                                )}
                                {campaign.status === "completed" && (
                                    <button
                                        className="btn-secondary"
                                        style={{ flex: 1, padding: "8px 0" }}
                                        onClick={(e) => handleReset(campaign.id, e)}
                                        title="Reset campaign to draft and re-run all contacts"
                                    >
                                        ↻ Reset & Re-run
                                    </button>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* New Campaign Modal */}
            {showNewCampaign && (
                <div
                    style={{
                        position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
                        background: "rgba(0, 0, 0, 0.7)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100,
                    }}
                    onClick={() => setShowNewCampaign(false)}
                >
                    <div className="glass-card" style={{ padding: 32, width: 500 }} onClick={(e) => e.stopPropagation()}>
                        <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 20 }}>New Campaign</h2>

                        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                            <div>
                                <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, display: "block" }}>Campaign Name</label>
                                <input
                                    className="input"
                                    placeholder="e.g. Q1 Renewal Outreach"
                                    value={newCampaignName}
                                    onChange={(e) => setNewCampaignName(e.target.value)}
                                />
                            </div>

                            <div>
                                <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, display: "block" }}>Select Agent</label>
                                <select
                                    className="input"
                                    value={selectedAgentId}
                                    onChange={(e) => setSelectedAgentId(e.target.value)}
                                >
                                    <option value="">-- Choose an Agent --</option>
                                    {agents?.map(agent => (
                                        <option key={agent.id} value={agent.id}>{agent.name}</option>
                                    ))}
                                </select>
                            </div>

                            <div>
                                <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, display: "block" }}>Upload Contacts (CSV)</label>
                                <div
                                    style={{
                                        padding: "32px", border: "2px dashed var(--border)", borderRadius: 12,
                                        textAlign: "center", cursor: "pointer",
                                        color: contactFile ? "var(--text-primary)" : "var(--text-muted)",
                                        fontSize: 14,
                                        background: contactFile ? "rgba(59, 130, 246, 0.1)" : "transparent"
                                    }}
                                    onClick={() => fileInputRef.current?.click()}
                                >
                                    {contactFile ? `📄 ${contactFile.name}` : "📁 Drop CSV or click to upload"}
                                    <div style={{ fontSize: 11, marginTop: 4, opacity: 0.7 }}>Column 'phone' required</div>
                                </div>
                                <input
                                    type="file"
                                    ref={fileInputRef}
                                    accept=".csv"
                                    style={{ display: "none" }}
                                    onChange={(e) => {
                                        if (e.target.files?.[0]) setContactFile(e.target.files[0]);
                                    }}
                                />
                            </div>

                            <div style={{ display: "flex", gap: 12, justifyContent: "flex-end", marginTop: 8 }}>
                                <button className="btn-danger" onClick={() => setShowNewCampaign(false)} disabled={isCreating}>Cancel</button>
                                <button className="btn-primary" onClick={handleCreate} disabled={isCreating}>
                                    {isCreating ? "Creating..." : "Create Campaign"}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
