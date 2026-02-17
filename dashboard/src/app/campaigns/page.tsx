"use client";

import { useState } from "react";

const MOCK_CAMPAIGNS = [
    {
        id: "cam-1",
        name: "Q1 Insurance Renewal",
        agent_id: "insurance_qualifier",
        status: "active",
        total_contacts: 250,
        called: 185,
        booked: 62,
        created_at: "2026-02-01",
    },
    {
        id: "cam-2",
        name: "New Patient Welcome",
        agent_id: "medical_receptionist",
        status: "completed",
        total_contacts: 100,
        called: 100,
        booked: 38,
        created_at: "2026-01-15",
    },
    {
        id: "cam-3",
        name: "Valentine's Dinner Promo",
        agent_id: "restaurant_host",
        status: "paused",
        total_contacts: 300,
        called: 45,
        booked: 12,
        created_at: "2026-02-10",
    },
];

const STATUS_BADGE: Record<string, string> = {
    active: "badge-success",
    completed: "badge-info",
    paused: "badge-warning",
    draft: "badge-danger",
};

export default function CampaignsPage() {
    const [showNewCampaign, setShowNewCampaign] = useState(false);

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

            {/* Campaign Cards */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))", gap: 16 }}>
                {MOCK_CAMPAIGNS.map((campaign) => {
                    const pct = Math.round((campaign.called / campaign.total_contacts) * 100);
                    const convRate = Math.round((campaign.booked / campaign.called) * 100);
                    return (
                        <div key={campaign.id} className="glass-card" style={{ padding: 24 }}>
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
                                <div>
                                    <div style={{ fontSize: 16, fontWeight: 600, color: "var(--text-primary)", marginBottom: 4 }}>
                                        {campaign.name}
                                    </div>
                                    <div style={{ fontSize: 12, color: "var(--text-muted)", textTransform: "capitalize" }}>
                                        Agent: {campaign.agent_id.replace(/_/g, " ")}
                                    </div>
                                </div>
                                <span className={`badge ${STATUS_BADGE[campaign.status]}`}>
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
                            <div style={{ display: "flex", gap: 20 }}>
                                <div>
                                    <div style={{ fontSize: 20, fontWeight: 700, color: "var(--text-primary)" }}>{campaign.booked}</div>
                                    <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Booked</div>
                                </div>
                                <div>
                                    <div style={{ fontSize: 20, fontWeight: 700, color: "var(--text-primary)" }}>{convRate}%</div>
                                    <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Conversion</div>
                                </div>
                                <div>
                                    <div style={{ fontSize: 20, fontWeight: 700, color: "var(--text-primary)" }}>{campaign.called}</div>
                                    <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Called</div>
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* New Campaign Modal (simplified placeholder) */}
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
                                <input className="input" placeholder="e.g. Q1 Renewal Outreach" />
                            </div>
                            <div>
                                <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, display: "block" }}>Agent</label>
                                <select className="input">
                                    <option>Insurance Lead Qualifier</option>
                                    <option>Medical Receptionist</option>
                                    <option>Restaurant Host</option>
                                </select>
                            </div>
                            <div>
                                <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, display: "block" }}>Upload Contacts (CSV)</label>
                                <div
                                    style={{
                                        padding: "32px", border: "2px dashed var(--border)", borderRadius: 12,
                                        textAlign: "center", cursor: "pointer", color: "var(--text-muted)", fontSize: 14,
                                    }}
                                >
                                    📁 Drop CSV file here or click to upload
                                </div>
                            </div>
                            <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
                                <button className="btn-danger" onClick={() => setShowNewCampaign(false)}>Cancel</button>
                                <button className="btn-primary">Create Campaign</button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
