"use client";

import { useState, useEffect } from "react";
import useSWR from "swr";
import { Save, RotateCcw, Loader2, CheckCircle, Phone, Globe, Cloud, ShieldCheck, Code, Key } from "lucide-react";
import { toast } from "sonner";
import { API_BASE_URL, fetcher, saveSettings, rollApiKey } from "@/lib/api";
import PageHeader from "@/components/ui/PageHeader";

interface Settings {
    // Editable
    business_name: string;
    owner_email: string;
    public_url: string;
    telephony_provider: string;
    backup_provider: string;
    // Telnyx (masked on read, editable on save)
    telnyx_api_key_masked: string;
    telnyx_connection_id_masked: string;
    telnyx_phone: string;
    has_custom_telnyx: boolean;
    // Twilio (masked on read, editable on save)
    twilio_account_sid_masked: string;
    twilio_auth_token_masked: string;
    twilio_phone: string;
    has_custom_twilio: boolean;
    // Webhooks & Integrations
    webhook_url: string;
    api_key_masked: string;
    has_api_key: boolean;
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

    // Providers
    const [telephonyProvider, setTelephonyProvider] = useState("telnyx");
    const [backupProvider, setBackupProvider] = useState("");

    // Telnyx editable state (blank = use server defaults)
    const [telnyxApiKey, setTelnyxApiKey] = useState("");
    const [telnyxConnectionId, setTelnyxConnectionId] = useState("");
    const [telnyxPhone, setTelnyxPhone] = useState("");

    // Twilio editable state
    const [twilioAccountSid, setTwilioAccountSid] = useState("");
    const [twilioAuthToken, setTwilioAuthToken] = useState("");
    const [twilioPhone, setTwilioPhone] = useState("");

    // Developer Integrations
    const [webhookUrl, setWebhookUrl] = useState("");
    const [newApiKey, setNewApiKey] = useState("");
    const [rollingKey, setRollingKey] = useState(false);

    // UI state
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);

    // Populate form when data arrives
    useEffect(() => {
        if (settings) {
            setBusinessName(settings.business_name);
            setOwnerEmail(settings.owner_email);
            setPublicUrl(settings.public_url);

            setTelephonyProvider(settings.telephony_provider || "telnyx");
            setBackupProvider(settings.backup_provider || "");

            setTelnyxPhone(settings.telnyx_phone);
            setTelnyxApiKey("");
            setTelnyxConnectionId("");

            setTwilioPhone(settings.twilio_phone);
            setTwilioAccountSid("");
            setTwilioAuthToken("");

            setWebhookUrl(settings.webhook_url || "");
            setNewApiKey("");
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
                telephony_provider: telephonyProvider,
                backup_provider: backupProvider,
            };
            // Only send fields if user explicitly typed something (secrets) or changed it (phone)
            if (telnyxApiKey) payload.telnyx_api_key = telnyxApiKey;
            if (telnyxConnectionId) payload.telnyx_connection_id = telnyxConnectionId;
            if (telnyxPhone !== (settings?.telnyx_phone ?? "")) payload.telnyx_phone = telnyxPhone;

            if (twilioAccountSid) payload.twilio_account_sid = twilioAccountSid;
            if (twilioAuthToken) payload.twilio_auth_token = twilioAuthToken;
            if (twilioPhone !== (settings?.twilio_phone ?? "")) payload.twilio_phone = twilioPhone;

            if (webhookUrl !== (settings?.webhook_url ?? "")) payload.webhook_url = webhookUrl;

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

    const handleRollKey = async () => {
        if (!confirm("Are you sure? Any existing applications using the active API key will immediately stop working.")) return;
        setRollingKey(true);
        try {
            const data = await rollApiKey();
            setNewApiKey(data.api_key);
            await refreshSettings();
            toast.success("API Key rolled successfully.");
        } catch (err: unknown) {
            toast.error(`Failed to roll API key: ${(err as Error).message}`);
        } finally {
            setRollingKey(false);
        }
    };

    const handleReset = () => {
        if (settings) {
            setBusinessName(settings.business_name);
            setOwnerEmail(settings.owner_email);
            setPublicUrl(settings.public_url);
            setTelephonyProvider(settings.telephony_provider || "telnyx");
            setBackupProvider(settings.backup_provider || "");

            setTelnyxPhone(settings.telnyx_phone);
            setTelnyxApiKey("");
            setTelnyxConnectionId("");

            setTwilioPhone(settings.twilio_phone);
            setTwilioAccountSid("");
            setTwilioAuthToken("");

            setWebhookUrl(settings.webhook_url || "");
            setNewApiKey("");
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

            {/* Provider Strategy — Editable */}
            <div className="glass-card p-6 mb-5">
                <div className="flex items-center gap-2.5 mb-4">
                    <div className="w-8 h-8 rounded-lg bg-indigo-500/15 flex items-center justify-center">
                        <Phone className="w-4 h-4 text-indigo-400" />
                    </div>
                    <div className="flex-1">
                        <h3 className="text-[15px] font-semibold">Telephony Providers</h3>
                        <span className="text-[11px] text-[var(--text-muted)]">Active engine & failover strategy</span>
                    </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <label className="text-[13px] text-[var(--text-muted)] mb-1.5 block">Primary Provider</label>
                        <select
                            className="input"
                            value={telephonyProvider}
                            onChange={(e) => setTelephonyProvider(e.target.value)}
                        >
                            <option value="telnyx">Telnyx (Recommended)</option>
                            <option value="twilio">Twilio</option>
                        </select>
                    </div>
                    <div>
                        <label className="text-[13px] text-[var(--text-muted)] mb-1.5 block">Backup Provider (Failover)</label>
                        <select
                            className="input"
                            value={backupProvider}
                            onChange={(e) => setBackupProvider(e.target.value)}
                        >
                            <option value="">None (Disable Failover)</option>
                            <option value="telnyx" disabled={telephonyProvider === "telnyx"}>Telnyx</option>
                            <option value="twilio" disabled={telephonyProvider === "twilio"}>Twilio</option>
                        </select>
                    </div>
                </div>
                <p className="text-xs text-[var(--text-muted)] mt-4">
                    Superactive will attempt outbound calls with your Primary provider first. If the request fails or times out, the call will instantly reroute through the Backup provider.
                </p>
            </div>

            {/* Telnyx — Editable */}
            <div className="glass-card p-6 mb-5">
                <div className="flex items-center gap-2.5 mb-4">
                    <div className="flex-1">
                        <h3 className="text-[15px] font-semibold">Telnyx Credentials</h3>
                    </div>
                    {settings.has_custom_telnyx && (
                        <span className="flex items-center gap-1 text-[11px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full">
                            <ShieldCheck className="w-3 h-3" />
                            Configured locally
                        </span>
                    )}
                </div>
                <div className="grid grid-cols-2 gap-4">
                    <div className="col-span-2">
                        <label className="text-[13px] text-[var(--text-muted)] mb-1.5 block">API Key</label>
                        <input
                            className="input"
                            value={telnyxApiKey}
                            onChange={(e) => setTelnyxApiKey(e.target.value)}
                            placeholder={settings.telnyx_api_key_masked || "Leave blank for server default"}
                            type="password"
                        />
                    </div>
                    <div>
                        <label className="text-[13px] text-[var(--text-muted)] mb-1.5 block">Connection ID</label>
                        <input
                            className="input"
                            value={telnyxConnectionId}
                            onChange={(e) => setTelnyxConnectionId(e.target.value)}
                            placeholder={settings.telnyx_connection_id_masked || "Leave blank for server default"}
                        />
                    </div>
                    <div>
                        <label className="text-[13px] text-[var(--text-muted)] mb-1.5 block">Phone Number</label>
                        <input
                            className="input"
                            value={telnyxPhone}
                            onChange={(e) => setTelnyxPhone(e.target.value)}
                            placeholder="+1234567890"
                        />
                    </div>
                </div>
            </div>

            {/* Twilio — Editable */}
            <div className="glass-card p-6 mb-5">
                <div className="flex items-center gap-2.5 mb-4">
                    <div className="flex-1">
                        <h3 className="text-[15px] font-semibold">Twilio Credentials</h3>
                    </div>
                    {settings.has_custom_twilio && (
                        <span className="flex items-center gap-1 text-[11px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full">
                            <ShieldCheck className="w-3 h-3" />
                            Configured locally
                        </span>
                    )}
                </div>
                <div className="grid grid-cols-2 gap-4">
                    <div className="col-span-2">
                        <label className="text-[13px] text-[var(--text-muted)] mb-1.5 block">Auth Token</label>
                        <input
                            className="input"
                            value={twilioAuthToken}
                            onChange={(e) => setTwilioAuthToken(e.target.value)}
                            placeholder={settings.twilio_auth_token_masked || "Leave blank for server default"}
                            type="password"
                        />
                    </div>
                    <div>
                        <label className="text-[13px] text-[var(--text-muted)] mb-1.5 block">Account SID</label>
                        <input
                            className="input"
                            value={twilioAccountSid}
                            onChange={(e) => setTwilioAccountSid(e.target.value)}
                            placeholder={settings.twilio_account_sid_masked || "Leave blank for server default"}
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
                    <label className="text-[13px] text-[var(--text-muted)] mb-1.5 block">Public URL (for Telnyx webhooks)</label>
                    <input
                        className="input"
                        value={publicUrl}
                        onChange={(e) => setPublicUrl(e.target.value)}
                    />
                    <p className="text-xs text-[var(--text-muted)] mt-1.5">
                        Your Cloudflare Tunnel or production domain. Used by Telnyx to reach your server.
                    </p>
                </div>
            </div>

            {/* Developers & Integrations */}
            <div className="glass-card p-6 mb-5 border border-indigo-500/10">
                <div className="flex items-center gap-2.5 mb-4">
                    <div className="w-8 h-8 rounded-lg bg-emerald-500/15 flex items-center justify-center">
                        <Code className="w-4 h-4 text-emerald-400" />
                    </div>
                    <div>
                        <h3 className="text-[15px] font-semibold">Developers & Integrations</h3>
                        <span className="text-[11px] text-[var(--text-muted)]">Webhooks and API access</span>
                    </div>
                </div>

                <div className="space-y-5">
                    {/* API Key */}
                    <div>
                        <label className="text-[13px] text-[var(--text-muted)] mb-1.5 block">Secret API Key</label>
                        {newApiKey ? (
                            <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg">
                                <p className="text-xs text-emerald-400 mb-2 font-medium">Please copy this key now. You will not be able to see it again.</p>
                                <div className="flex items-center gap-2">
                                    <code className="flex-1 bg-black/40 px-2.5 py-1.5 rounded text-sm text-[var(--text-primary)] font-mono tracking-wide break-all">
                                        {newApiKey}
                                    </code>
                                </div>
                            </div>
                        ) : (
                            <div className="flex items-center gap-3">
                                <input
                                    className="input font-mono flex-1 opacity-70"
                                    value={settings.has_api_key ? settings.api_key_masked : "No key generated"}
                                    readOnly
                                    disabled
                                />
                                <button
                                    className="btn-secondary flex items-center gap-1.5 shrink-0"
                                    onClick={handleRollKey}
                                    disabled={rollingKey}
                                >
                                    {rollingKey ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Key className="w-3.5 h-3.5" />}
                                    {settings.has_api_key ? "Roll Key" : "Generate Key"}
                                </button>
                            </div>
                        )}
                        <p className="text-xs text-[var(--text-muted)] mt-1.5">
                            Used to authenticate API requests to Superactive and sign outgoing webhooks.
                        </p>
                    </div>

                    <div className="h-px bg-[var(--border)]" />

                    {/* Webhook URL */}
                    <div>
                        <label className="text-[13px] text-[var(--text-muted)] mb-1.5 block">Post-Call Webhook URL</label>
                        <input
                            className="input"
                            value={webhookUrl}
                            onChange={(e) => setWebhookUrl(e.target.value)}
                            placeholder="https://your-server.com/webhooks/superactive"
                        />
                        <p className="text-xs text-[var(--text-muted)] mt-1.5">
                            We will POST a JSON payload (call transcript, variables, metrics) to this URL when a call completes.
                        </p>
                    </div>
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
