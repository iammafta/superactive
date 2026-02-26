"use client";

import { useState, useEffect } from "react";
import useSWR from "swr";
import { Save, RotateCcw, Loader2, CheckCircle, Phone, Globe, Cloud, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { API_BASE_URL, fetcher, saveSettings } from "@/lib/api";
import PageHeader from "@/components/ui/PageHeader";

interface Settings {
    // Editable
    business_name: string;
    owner_email: string;
    public_url: string;
    // Twilio (masked on read, editable on save)
    twilio_sid_masked: string;
    twilio_token_masked: string;
    twilio_phone: string;
    has_custom_twilio: boolean;
    // Read-only
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

    // Twilio editable state (blank = use server defaults)
    const [twilioSid, setTwilioSid] = useState("");
    const [twilioToken, setTwilioToken] = useState("");
    const [twilioPhone, setTwilioPhone] = useState("");

    // UI state
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);

    // Populate form when data arrives
    useEffect(() => {
        if (settings) {
            setBusinessName(settings.business_name);
            setOwnerEmail(settings.owner_email);
            setPublicUrl(settings.public_url);
            setTwilioPhone(settings.twilio_phone);
            // SID and token show masked values as placeholders, start blank
            setTwilioSid("");
            setTwilioToken("");
        }
    }, [settings]);

    const handleSave = async () => {
        setSaving(true);
        setSaved(false);
        try {
            const payload: Record<string, string> = {
                business_name: businessName,
                owner_email: ownerEmail,
                public_url: publicUrl,
            };
            // Only send Twilio fields if user explicitly typed something
            if (twilioSid) payload.twilio_sid = twilioSid;
            if (twilioToken) payload.twilio_token = twilioToken;
            if (twilioPhone !== (settings?.twilio_phone ?? "")) payload.twilio_phone = twilioPhone;
            await saveSettings(payload);
            await refreshSettings();
            setSaved(true);
            toast.success("Settings saved successfully!");
            setTimeout(() => setSaved(false), 3000);
        } catch (err: unknown) {
            toast.error(`Failed to save settings: ${(err as Error).message}`);
        } finally {
            setSaving(false);
        }
    };

    const handleReset = () => {
        if (settings) {
            setBusinessName(settings.business_name);
            setOwnerEmail(settings.owner_email);
            setPublicUrl(settings.public_url);
            setTwilioPhone(settings.twilio_phone);
            setTwilioSid("");
            setTwilioToken("");
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
        <div className="max-w-[700px] mx-auto">
            <PageHeader
                title="Settings"
                description="Platform configuration and integrations"
            />

            {/* Account — Editable */}
            <div className="glass-card p-6 mb-5">
                <h3 className="text-[15px] font-semibold mb-4">Account</h3>
                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <label className="text-[13px] text-[var(--text-muted)] mb-1.5 block">Business Name</label>
                        <input
                            className="input"
                            value={businessName}
                            onChange={(e) => setBusinessName(e.target.value)}
                        />
                    </div>
                    <div>
                        <label className="text-[13px] text-[var(--text-muted)] mb-1.5 block">Owner Email</label>
                        <input
                            className="input"
                            value={ownerEmail}
                            onChange={(e) => setOwnerEmail(e.target.value)}
                            type="email"
                        />
                    </div>
                </div>
            </div>

            {/* Twilio — Editable */}
            <div className="glass-card p-6 mb-5">
                <div className="flex items-center gap-2.5 mb-4">
                    <div className="w-8 h-8 rounded-lg bg-red-500/15 flex items-center justify-center">
                        <Phone className="w-4 h-4 text-red-400" />
                    </div>
                    <div className="flex-1">
                        <h3 className="text-[15px] font-semibold">Twilio Integration</h3>
                        <span className="text-[11px] text-[var(--text-muted)]">Telephony provider</span>
                    </div>
                    {settings.has_custom_twilio && (
                        <span className="flex items-center gap-1 text-[11px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full">
                            <ShieldCheck className="w-3 h-3" />
                            Custom credentials
                        </span>
                    )}
                </div>
                <div className="flex flex-col gap-4">
                    <div>
                        <label className="text-[13px] text-[var(--text-muted)] mb-1.5 block">Account SID</label>
                        <input
                            className="input"
                            value={twilioSid}
                            onChange={(e) => setTwilioSid(e.target.value)}
                            placeholder={settings.twilio_sid_masked || "Leave blank for server default"}
                        />
                    </div>
                    <div>
                        <label className="text-[13px] text-[var(--text-muted)] mb-1.5 block">Auth Token</label>
                        <input
                            className="input"
                            value={twilioToken}
                            onChange={(e) => setTwilioToken(e.target.value)}
                            placeholder={settings.twilio_token_masked || "Leave blank for server default"}
                            type="password"
                        />
                    </div>
                    <div>
                        <label className="text-[13px] text-[var(--text-muted)] mb-1.5 block">Phone Number</label>
                        <input
                            className="input"
                            value={twilioPhone}
                            onChange={(e) => setTwilioPhone(e.target.value)}
                            placeholder="+1234567890"
                        />
                    </div>
                    <p className="text-xs text-[var(--text-muted)]">
                        Leave fields blank to use server-configured defaults. Only fill in to override with your own Twilio account.
                    </p>
                </div>
            </div>

            {/* Server — Editable */}
            <div className="glass-card p-6 mb-5">
                <div className="flex items-center gap-2.5 mb-4">
                    <div className="w-8 h-8 rounded-lg bg-blue-500/15 flex items-center justify-center">
                        <Globe className="w-4 h-4 text-blue-400" />
                    </div>
                    <h3 className="text-[15px] font-semibold">Server Configuration</h3>
                </div>
                <div>
                    <label className="text-[13px] text-[var(--text-muted)] mb-1.5 block">Public URL (for Twilio webhooks)</label>
                    <input
                        className="input"
                        value={publicUrl}
                        onChange={(e) => setPublicUrl(e.target.value)}
                    />
                    <p className="text-xs text-[var(--text-muted)] mt-1.5">
                        Your Cloudflare Tunnel or production domain. Used by Twilio to reach your server.
                    </p>
                </div>
            </div>

            {/* Google Cloud — Read-Only */}
            <div className="glass-card p-6 mb-5">
                <div className="flex items-center gap-2.5 mb-4">
                    <div className="w-8 h-8 rounded-lg bg-emerald-500/15 flex items-center justify-center">
                        <Cloud className="w-4 h-4 text-emerald-400" />
                    </div>
                    <div>
                        <h3 className="text-[15px] font-semibold">Google Cloud</h3>
                        <span className="text-[11px] text-[var(--text-muted)]">AI & Speech services</span>
                    </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <label className="text-[13px] text-[var(--text-muted)] mb-1.5 block">Project ID</label>
                        <input className="input opacity-60 cursor-not-allowed" value={settings.gcp_project} readOnly />
                    </div>
                    <div>
                        <label className="text-[13px] text-[var(--text-muted)] mb-1.5 block">Location</label>
                        <input className="input opacity-60 cursor-not-allowed" value={settings.gcp_location} readOnly />
                    </div>
                </div>
            </div>

            {/* Action Buttons */}
            <div className="flex justify-end gap-3 items-center">
                {saved && (
                    <span className="flex items-center gap-1.5 text-emerald-500 text-[13px]">
                        <CheckCircle className="w-4 h-4" />
                        Settings saved
                    </span>
                )}
                <button className="btn-danger flex items-center gap-1.5" onClick={handleReset}>
                    <RotateCcw className="w-3.5 h-3.5" />
                    Reset
                </button>
                <button className="btn-primary flex items-center gap-1.5" onClick={handleSave} disabled={saving}>
                    {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                    {saving ? "Saving..." : "Save Settings"}
                </button>
            </div>
        </div>
    );
}

