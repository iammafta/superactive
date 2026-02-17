"use client";

import { useState } from "react";

export default function SettingsPage() {
    const [twilioSid, setTwilioSid] = useState("AC••••••••••••••••••••");
    const [twilioToken, setTwilioToken] = useState("••••••••••••••••••••");
    const [twilioPhone, setTwilioPhone] = useState("+1 (845) 773-8193");
    const [publicUrl, setPublicUrl] = useState("https://your-domain.ngrok.app");

    return (
        <div style={{ maxWidth: 700, margin: "0 auto" }}>
            <div style={{ marginBottom: 28 }}>
                <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>Settings</h1>
                <p style={{ fontSize: 14, color: "var(--text-muted)" }}>Platform configuration and integrations</p>
            </div>

            {/* Account */}
            <div className="glass-card" style={{ padding: 24, marginBottom: 20 }}>
                <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Account</h3>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                    <div>
                        <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, display: "block" }}>Business Name</label>
                        <input className="input" defaultValue="Superactive Demo" />
                    </div>
                    <div>
                        <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, display: "block" }}>Owner Email</label>
                        <input className="input" defaultValue="admin@superactive.ai" type="email" />
                    </div>
                </div>
            </div>

            {/* Twilio */}
            <div className="glass-card" style={{ padding: 24, marginBottom: 20 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
                    <div style={{
                        width: 32, height: 32, borderRadius: 8,
                        background: "rgba(239, 68, 68, 0.15)", display: "flex",
                        alignItems: "center", justifyContent: "center", fontSize: 16,
                    }}>
                        📞
                    </div>
                    <h3 style={{ fontSize: 15, fontWeight: 600 }}>Twilio Integration</h3>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                    <div>
                        <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, display: "block" }}>Account SID</label>
                        <input className="input" value={twilioSid} onChange={(e) => setTwilioSid(e.target.value)} />
                    </div>
                    <div>
                        <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, display: "block" }}>Auth Token</label>
                        <input className="input" value={twilioToken} onChange={(e) => setTwilioToken(e.target.value)} type="password" />
                    </div>
                    <div>
                        <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, display: "block" }}>Phone Number</label>
                        <input className="input" value={twilioPhone} onChange={(e) => setTwilioPhone(e.target.value)} />
                    </div>
                </div>
            </div>

            {/* Server */}
            <div className="glass-card" style={{ padding: 24, marginBottom: 20 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
                    <div style={{
                        width: 32, height: 32, borderRadius: 8,
                        background: "rgba(59, 130, 246, 0.15)", display: "flex",
                        alignItems: "center", justifyContent: "center", fontSize: 16,
                    }}>
                        🌐
                    </div>
                    <h3 style={{ fontSize: 15, fontWeight: 600 }}>Server Configuration</h3>
                </div>
                <div>
                    <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, display: "block" }}>Public URL (for Twilio webhooks)</label>
                    <input className="input" value={publicUrl} onChange={(e) => setPublicUrl(e.target.value)} />
                    <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 6 }}>
                        Use your ngrok URL for local development or your production domain.
                    </p>
                </div>
            </div>

            {/* Google Cloud */}
            <div className="glass-card" style={{ padding: 24, marginBottom: 20 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
                    <div style={{
                        width: 32, height: 32, borderRadius: 8,
                        background: "rgba(16, 185, 129, 0.15)", display: "flex",
                        alignItems: "center", justifyContent: "center", fontSize: 16,
                    }}>
                        ☁️
                    </div>
                    <h3 style={{ fontSize: 15, fontWeight: 600 }}>Google Cloud</h3>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                    <div>
                        <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, display: "block" }}>Project ID</label>
                        <input className="input" defaultValue="divine-apogee-480205-h8" />
                    </div>
                    <div>
                        <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, display: "block" }}>Location</label>
                        <input className="input" defaultValue="us-central1" />
                    </div>
                </div>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 12 }}>
                <button className="btn-danger">Reset to Defaults</button>
                <button className="btn-primary">Save Settings</button>
            </div>
        </div>
    );
}
