"use client";

import { useState, useEffect } from "react";
import useSWR from "swr";
import { Save, RotateCcw, Loader2, CheckCircle } from "lucide-react";
import { API_BASE_URL, fetcher, saveSettings } from "@/lib/api";

interface Settings {
    // Editable
    business_name: string;
    owner_email: string;
    public_url: string;
    // Read-only (from env, masked)
    twilio_sid_masked: string;
    twilio_token_masked: string;
    twilio_phone: string;
    gcp_project: string;
    gcp_location: string;
}

export default function SettingsPage() {
    const { data: settings, error, mutate: refreshSettings } = useSWR<Settings>(
        `${API_BASE_URL}/settings`,
        fetcher
    );

    // Editable form state
    const [businessName, setBusinessName] = useState("");
    const [ownerEmail, setOwnerEmail] = useState("");
    const [publicUrl, setPublicUrl] = useState("");

    // UI state
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);

    // Populate form when data arrives
    useEffect(() => {
        if (settings) {
            setBusinessName(settings.business_name);
            setOwnerEmail(settings.owner_email);
            setPublicUrl(settings.public_url);
        }
    }, [settings]);

    const handleSave = async () => {
        setSaving(true);
        setSaved(false);
        try {
            await saveSettings({
                business_name: businessName,
                owner_email: ownerEmail,
                public_url: publicUrl,
            });
            await refreshSettings();
            setSaved(true);
            setTimeout(() => setSaved(false), 3000);
        } catch (err) {
            console.error("Failed to save settings:", err);
        } finally {
            setSaving(false);
        }
    };

    const handleReset = () => {
        if (settings) {
            setBusinessName(settings.business_name);
            setOwnerEmail(settings.owner_email);
            setPublicUrl(settings.public_url);
        }
    };

    if (error) return <div className="p-8 text-red-400">Failed to load settings.</div>;
    if (!settings) return (
        <div className="flex items-center justify-center h-screen text-gray-400 gap-3">
            <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
            Loading settings...
        </div>
    );

    return (
        <div style={{ maxWidth: 700, margin: "0 auto" }}>
            <div style={{ marginBottom: 28 }}>
                <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>Settings</h1>
                <p style={{ fontSize: 14, color: "var(--text-muted)" }}>Platform configuration and integrations</p>
            </div>

            {/* Account — Editable */}
            <div className="glass-card" style={{ padding: 24, marginBottom: 20 }}>
                <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Account</h3>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                    <div>
                        <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, display: "block" }}>Business Name</label>
                        <input
                            className="input"
                            value={businessName}
                            onChange={(e) => setBusinessName(e.target.value)}
                        />
                    </div>
                    <div>
                        <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, display: "block" }}>Owner Email</label>
                        <input
                            className="input"
                            value={ownerEmail}
                            onChange={(e) => setOwnerEmail(e.target.value)}
                            type="email"
                        />
                    </div>
                </div>
            </div>

            {/* Twilio — Read-Only */}
            <div className="glass-card" style={{ padding: 24, marginBottom: 20 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
                    <div style={{
                        width: 32, height: 32, borderRadius: 8,
                        background: "rgba(239, 68, 68, 0.15)", display: "flex",
                        alignItems: "center", justifyContent: "center", fontSize: 16,
                    }}>
                        📞
                    </div>
                    <div>
                        <h3 style={{ fontSize: 15, fontWeight: 600 }}>Twilio Integration</h3>
                        <span style={{ fontSize: 11, color: "var(--text-muted)" }}>Configured via .env file</span>
                    </div>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                    <div>
                        <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, display: "block" }}>Account SID</label>
                        <input className="input" value={settings.twilio_sid_masked} readOnly
                            style={{ opacity: 0.6, cursor: "not-allowed" }} />
                    </div>
                    <div>
                        <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, display: "block" }}>Auth Token</label>
                        <input className="input" value={settings.twilio_token_masked} readOnly type="password"
                            style={{ opacity: 0.6, cursor: "not-allowed" }} />
                    </div>
                    <div>
                        <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, display: "block" }}>Phone Number</label>
                        <input className="input" value={settings.twilio_phone} readOnly
                            style={{ opacity: 0.6, cursor: "not-allowed" }} />
                    </div>
                </div>
            </div>

            {/* Server — Editable */}
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
                    <input
                        className="input"
                        value={publicUrl}
                        onChange={(e) => setPublicUrl(e.target.value)}
                    />
                    <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 6 }}>
                        Your Cloudflare Tunnel or production domain. Used by Twilio to reach your server.
                    </p>
                </div>
            </div>

            {/* Google Cloud — Read-Only */}
            <div className="glass-card" style={{ padding: 24, marginBottom: 20 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
                    <div style={{
                        width: 32, height: 32, borderRadius: 8,
                        background: "rgba(16, 185, 129, 0.15)", display: "flex",
                        alignItems: "center", justifyContent: "center", fontSize: 16,
                    }}>
                        ☁️
                    </div>
                    <div>
                        <h3 style={{ fontSize: 15, fontWeight: 600 }}>Google Cloud</h3>
                        <span style={{ fontSize: 11, color: "var(--text-muted)" }}>Configured via .env file</span>
                    </div>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                    <div>
                        <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, display: "block" }}>Project ID</label>
                        <input className="input" value={settings.gcp_project} readOnly
                            style={{ opacity: 0.6, cursor: "not-allowed" }} />
                    </div>
                    <div>
                        <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, display: "block" }}>Location</label>
                        <input className="input" value={settings.gcp_location} readOnly
                            style={{ opacity: 0.6, cursor: "not-allowed" }} />
                    </div>
                </div>
            </div>

            {/* Action Buttons */}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, alignItems: "center" }}>
                {saved && (
                    <span style={{ display: "flex", alignItems: "center", gap: 6, color: "#10b981", fontSize: 13 }}>
                        <CheckCircle size={16} />
                        Settings saved
                    </span>
                )}
                <button className="btn-danger" onClick={handleReset} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <RotateCcw size={14} />
                    Reset
                </button>
                <button className="btn-primary" onClick={handleSave} disabled={saving}
                    style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                    {saving ? "Saving..." : "Save Settings"}
                </button>
            </div>
        </div>
    );
}
