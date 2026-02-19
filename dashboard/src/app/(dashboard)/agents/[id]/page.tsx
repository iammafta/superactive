"use client";

import { useState, useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import useSWR from "swr";
import {
    ArrowLeft, Save, Phone, Loader2, Plus, Trash2, ChevronDown,
    ChevronUp, GripVertical, ArrowRight, X, AlertCircle,
} from "lucide-react";
import { API_BASE_URL, fetcher, createAgent, updateAgent } from "@/lib/api";
import type { AgentConfig, StateConfig } from "@/lib/types";
import TestCallModal from "@/components/TestCallModal";

const ALL_TOOLS = [
    { id: "book_appointment", label: "Book Appointment", icon: "📅", desc: "Schedule appointments via calendar" },
    { id: "check_availability", label: "Check Availability", icon: "📋", desc: "Query open time slots" },
    { id: "transfer_to_human", label: "Transfer to Human", icon: "🔄", desc: "Warm transfer to live agent" },
    { id: "send_followup_sms", label: "Send Follow-up SMS", icon: "📱", desc: "Send SMS via Twilio" },
    { id: "log_lead", label: "Log Lead", icon: "📝", desc: "Save lead for follow-up" },
    { id: "lookup_client", label: "Lookup Client", icon: "🔍", desc: "Check returning caller" },
    { id: "call_business_api", label: "Business API", icon: "🌐", desc: "Query custom webhook" },
    { id: "google_search", label: "Google Search", icon: "🔎", desc: "Real-time web search" },
];

const VOICE_OPTIONS = [
    { id: "en-US-Chirp3-HD-Charon", label: "Charon (Warm, Male)" },
    { id: "en-US-Chirp3-HD-Leda", label: "Leda (Professional, Female)" },
    { id: "en-US-Chirp3-HD-Zephyr", label: "Zephyr (Friendly, Male)" },
    { id: "en-US-Chirp3-HD-Fenrir", label: "Fenrir (Confident, Male)" },
    { id: "en-US-Chirp3-HD-Aoede", label: "Aoede (Calm, Female)" },
    { id: "en-US-Standard-C", label: "Standard C (Basic Female)" },
];

const BUSINESS_TYPES = [
    "restaurant", "medical", "insurance", "legal", "real_estate",
    "salon", "dental", "automotive", "general", "custom",
];

function guardrailLabel(level: number): string {
    if (level >= 0.8) return "Strict Script";
    if (level >= 0.5) return "Guided";
    if (level >= 0.2) return "Flexible";
    return "Free Talk";
}

const DEFAULT_FORM: Partial<AgentConfig> = {
    name: "",
    business_type: "custom",
    guardrail_level: 0.5,
    greeting: "Hello, how can I help you today?",
    system_prompt: "",
    allowed_tools: ["transfer_to_human"],
    escalation_triggers: ["speak to a human", "transfer me", "manager"],
    voice_id: "en-US-Chirp3-HD-Charon",
    max_turns: 20,
    max_duration_seconds: 300,
    active: true,
    description: "",
    states: [],
    webhook_url: null,
    webhook_headers: {},
};

// ── State Builder Component ──────────────────────────────────────

function StateCard({
    state,
    index,
    allStates,
    expanded,
    onToggle,
    onChange,
    onDelete,
    onMoveUp,
    onMoveDown,
    isFirst,
    isLast,
}: {
    state: StateConfig;
    index: number;
    allStates: StateConfig[];
    expanded: boolean;
    onToggle: () => void;
    onChange: (s: StateConfig) => void;
    onDelete: () => void;
    onMoveUp: () => void;
    onMoveDown: () => void;
    isFirst: boolean;
    isLast: boolean;
}) {
    const otherStates = allStates.filter((_, i) => i !== index);

    const updateTransition = (key: string, value: string, oldKey?: string) => {
        const t = { ...state.transitions };
        if (oldKey && oldKey !== key) delete t[oldKey];
        t[key] = value;
        onChange({ ...state, transitions: t });
    };

    const removeTransition = (key: string) => {
        const t = { ...state.transitions };
        delete t[key];
        onChange({ ...state, transitions: t });
    };

    const addTransition = () => {
        const t = { ...state.transitions };
        t[`trigger_${Object.keys(t).length + 1}`] = otherStates[0]?.name || "";
        onChange({ ...state, transitions: t });
    };

    const addRequiredInfo = (info: string) => {
        if (info && !state.required_info.includes(info)) {
            onChange({ ...state, required_info: [...state.required_info, info] });
        }
    };

    const removeRequiredInfo = (info: string) => {
        onChange({ ...state, required_info: state.required_info.filter(i => i !== info) });
    };

    return (
        <div className="glass-card" style={{ padding: 0, overflow: "hidden" }}>
            {/* Header (always visible) */}
            <div
                onClick={onToggle}
                style={{
                    display: "flex", alignItems: "center", gap: 12, padding: "14px 16px",
                    cursor: "pointer", borderBottom: expanded ? "1px solid rgba(255,255,255,0.05)" : "none",
                }}
            >
                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                    {!isFirst && (
                        <button onClick={(e) => { e.stopPropagation(); onMoveUp(); }}
                            style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", padding: 0, lineHeight: 1 }}>
                            <ChevronUp className="w-3 h-3" />
                        </button>
                    )}
                    {!isLast && (
                        <button onClick={(e) => { e.stopPropagation(); onMoveDown(); }}
                            style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", padding: 0, lineHeight: 1 }}>
                            <ChevronDown className="w-3 h-3" />
                        </button>
                    )}
                </div>
                <div style={{
                    width: 28, height: 28, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center",
                    background: "rgba(59, 130, 246, 0.1)", color: "#3b82f6", fontSize: 13, fontWeight: 700,
                }}>{index + 1}</div>
                <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)" }}>{state.name || "Unnamed State"}</div>
                    <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>
                        {Object.keys(state.transitions).length} transitions · {state.max_turns} max turns
                        {state.required_info.length > 0 && ` · ${state.required_info.length} fields`}
                    </div>
                </div>
                <button onClick={(e) => { e.stopPropagation(); onDelete(); }}
                    style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", padding: 4 }}>
                    <Trash2 className="w-4 h-4" />
                </button>
                {expanded ? <ChevronUp className="w-4 h-4 text-gray-500" /> : <ChevronDown className="w-4 h-4 text-gray-500" />}
            </div>

            {/* Expanded Editor */}
            {expanded && (
                <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
                    {/* State Name */}
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                        <div>
                            <label style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 4, display: "block" }}>State Name</label>
                            <input className="input" value={state.name}
                                onChange={(e) => onChange({ ...state, name: e.target.value })}
                                placeholder="e.g. greeting, qualifying, booking" />
                        </div>
                        <div>
                            <label style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 4, display: "block" }}>Max Turns</label>
                            <input className="input" type="number" min={1} max={20} value={state.max_turns}
                                onChange={(e) => onChange({ ...state, max_turns: parseInt(e.target.value) || 5 })} />
                        </div>
                    </div>

                    {/* Instructions */}
                    <div>
                        <label style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 4, display: "block" }}>Instructions</label>
                        <textarea className="input" value={state.instructions}
                            onChange={(e) => onChange({ ...state, instructions: e.target.value })}
                            placeholder="What should the agent do in this state?"
                            style={{ minHeight: 80 }} />
                    </div>

                    {/* Required Info Tags */}
                    <div>
                        <label style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 4, display: "block" }}>Required Info</label>
                        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 8 }}>
                            {state.required_info.map((info) => (
                                <span key={info} style={{
                                    display: "inline-flex", alignItems: "center", gap: 4, padding: "4px 10px",
                                    background: "rgba(59, 130, 246, 0.1)", border: "1px solid rgba(59, 130, 246, 0.2)",
                                    borderRadius: 6, fontSize: 12, color: "#60a5fa",
                                }}>
                                    {info}
                                    <button onClick={() => removeRequiredInfo(info)}
                                        style={{ background: "none", border: "none", color: "#60a5fa", cursor: "pointer", padding: 0, lineHeight: 1 }}>
                                        <X className="w-3 h-3" />
                                    </button>
                                </span>
                            ))}
                        </div>
                        <input className="input" placeholder="Type field name and press Enter"
                            style={{ fontSize: 13 }}
                            onKeyDown={(e) => {
                                if (e.key === "Enter") {
                                    e.preventDefault();
                                    const val = (e.target as HTMLInputElement).value.trim();
                                    if (val) { addRequiredInfo(val); (e.target as HTMLInputElement).value = ""; }
                                }
                            }} />
                    </div>

                    {/* Transitions */}
                    <div>
                        <label style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8, display: "block" }}>Transitions</label>
                        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                            {Object.entries(state.transitions).map(([trigger, target]) => (
                                <div key={trigger} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                    <input className="input" value={trigger} style={{ flex: 1, fontSize: 13 }}
                                        placeholder="Trigger name"
                                        onChange={(e) => updateTransition(e.target.value, target, trigger)} />
                                    <ArrowRight className="w-4 h-4 text-gray-500 shrink-0" />
                                    <select className="input" value={target} style={{ flex: 1, fontSize: 13 }}
                                        onChange={(e) => updateTransition(trigger, e.target.value)}>
                                        <option value="">Select state...</option>
                                        {allStates.map((s) => (
                                            <option key={s.name} value={s.name}>{s.name}</option>
                                        ))}
                                    </select>
                                    <button onClick={() => removeTransition(trigger)}
                                        style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", padding: 4 }}>
                                        <X className="w-4 h-4" />
                                    </button>
                                </div>
                            ))}
                        </div>
                        <button onClick={addTransition}
                            style={{
                                marginTop: 8, display: "flex", alignItems: "center", gap: 6, padding: "6px 12px",
                                background: "rgba(59, 130, 246, 0.08)", border: "1px solid rgba(59, 130, 246, 0.2)",
                                borderRadius: 8, color: "#60a5fa", fontSize: 12, fontWeight: 600, cursor: "pointer",
                            }}>
                            <Plus className="w-3 h-3" /> Add Transition
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}

// ── Visual Flow Preview ──────────────────────────────────────────

function StateFlowPreview({ states }: { states: StateConfig[] }) {
    if (states.length === 0) return null;
    return (
        <div style={{ display: "flex", alignItems: "center", gap: 4, flexWrap: "wrap", padding: "12px 0" }}>
            {states.map((state, i) => (
                <div key={state.name || i} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                    <div style={{
                        padding: "6px 14px", borderRadius: 8, fontSize: 12, fontWeight: 600,
                        background: i === 0 ? "rgba(16, 185, 129, 0.15)" : "rgba(59, 130, 246, 0.1)",
                        border: `1px solid ${i === 0 ? "rgba(16, 185, 129, 0.3)" : "rgba(59, 130, 246, 0.2)"}`,
                        color: i === 0 ? "#34d399" : "#60a5fa",
                    }}>{state.name || `State ${i + 1}`}</div>
                    {i < states.length - 1 && <ArrowRight className="w-4 h-4 text-gray-600" />}
                </div>
            ))}
        </div>
    );
}

// ── Main Page ────────────────────────────────────────────────────

export default function AgentEditorPage() {
    const router = useRouter();
    const params = useParams();
    const agentId = params.id as string;
    const isNew = agentId === "new";

    const { data: existingAgent, error, isLoading } = useSWR<AgentConfig>(
        isNew ? null : `${API_BASE_URL}/agents/${agentId}`,
        fetcher
    );

    const [form, setForm] = useState<Partial<AgentConfig>>({ ...DEFAULT_FORM });
    const [saving, setSaving] = useState(false);
    const [saveError, setSaveError] = useState("");
    const [showTestModal, setShowTestModal] = useState(false);
    const [expandedState, setExpandedState] = useState<number | null>(null);

    useEffect(() => {
        if (existingAgent) {
            setForm(existingAgent);
        }
    }, [existingAgent]);

    const updateField = <K extends keyof AgentConfig>(key: K, value: AgentConfig[K]) => {
        setForm((prev) => ({ ...prev, [key]: value }));
    };

    const toggleTool = (toolId: string) => {
        const current = form.allowed_tools || [];
        if (current.includes(toolId)) {
            updateField("allowed_tools", current.filter(t => t !== toolId));
        } else {
            updateField("allowed_tools", [...current, toolId]);
        }
    };

    // State management helpers
    const addState = () => {
        const states = [...(form.states || [])];
        states.push({
            name: `state_${states.length + 1}`,
            instructions: "",
            transitions: {},
            max_turns: 5,
            required_info: [],
        });
        updateField("states", states);
        setExpandedState(states.length - 1);
    };

    const updateState = (index: number, state: StateConfig) => {
        const states = [...(form.states || [])];
        states[index] = state;
        updateField("states", states);
    };

    const deleteState = (index: number) => {
        const states = [...(form.states || [])];
        states.splice(index, 1);
        updateField("states", states);
        setExpandedState(null);
    };

    const moveState = (from: number, to: number) => {
        const states = [...(form.states || [])];
        const [moved] = states.splice(from, 1);
        states.splice(to, 0, moved);
        updateField("states", states);
        setExpandedState(to);
    };

    const handleSave = async () => {
        setSaving(true);
        setSaveError("");
        try {
            const id = isNew
                ? (form.name || "agent").toLowerCase().replace(/\s+/g, "_").replace(/[^a-z0-9_]/g, "")
                : agentId;
            const payload = { ...form, id };
            if (isNew) {
                await createAgent(payload);
            } else {
                await updateAgent(agentId, payload);
            }
            router.push("/agents");
        } catch (err: any) {
            setSaveError(err.message || "Failed to save");
        } finally {
            setSaving(false);
        }
    };

    if (!isNew && isLoading) return (
        <div className="flex items-center justify-center h-screen text-gray-400 gap-3">
            <Loader2 className="w-6 h-6 animate-spin text-blue-500" />Loading agent...
        </div>
    );
    if (!isNew && error) return (
        <div className="p-12 text-center text-red-400">
            <AlertCircle className="w-8 h-8 mx-auto mb-2" />Failed to load agent: {error.message}
        </div>
    );

    const derivedId = isNew
        ? (form.name || "agent").toLowerCase().replace(/\s+/g, "_").replace(/[^a-z0-9_]/g, "")
        : agentId;

    return (
        <div style={{ maxWidth: 900, margin: "0 auto" }}>
            {/* Header */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 28 }}>
                <div>
                    <button onClick={() => router.push("/agents")}
                        style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: 14, marginBottom: 8, padding: 0, display: "flex", alignItems: "center", gap: 6 }}>
                        <ArrowLeft className="w-4 h-4" /> Back to Agents
                    </button>
                    <h1 style={{ fontSize: 24, fontWeight: 700 }}>{isNew ? "Create Agent" : `Edit: ${form.name}`}</h1>
                    {isNew && form.name && (
                        <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>ID: {derivedId}</p>
                    )}
                </div>
                <div style={{ display: "flex", gap: 12 }}>
                    {!isNew && (
                        <button className="btn-primary" onClick={() => setShowTestModal(true)}
                            style={{ display: "flex", alignItems: "center", gap: 6, background: "rgba(59,130,246,0.15)", color: "#60a5fa", border: "1px solid rgba(59,130,246,0.3)" }}>
                            <Phone className="w-4 h-4" /> Test Call
                        </button>
                    )}
                    <button className="btn-primary" onClick={handleSave} disabled={saving}
                        style={{ display: "flex", alignItems: "center", gap: 6, opacity: saving ? 0.6 : 1 }}>
                        {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                        {saving ? "Saving..." : (isNew ? "Create Agent" : "Save Changes")}
                    </button>
                </div>
            </div>

            {saveError && (
                <div style={{
                    padding: "12px 16px", marginBottom: 16, borderRadius: 10,
                    background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)",
                    color: "#f87171", fontSize: 13, display: "flex", alignItems: "center", gap: 8,
                }}>
                    <AlertCircle className="w-4 h-4" /> {saveError}
                </div>
            )}

            {/* Agent Identity */}
            <div className="glass-card" style={{ padding: 24, marginBottom: 20 }}>
                <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Agent Identity</h3>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
                    <div>
                        <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, display: "block" }}>Agent Name</label>
                        <input className="input" value={form.name || ""} onChange={(e) => updateField("name", e.target.value)}
                            placeholder="e.g. Dr. Smith's Receptionist" />
                    </div>
                    <div>
                        <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, display: "block" }}>Business Type</label>
                        <select className="input" value={form.business_type || "custom"}
                            onChange={(e) => updateField("business_type", e.target.value)}>
                            {BUSINESS_TYPES.map(t => <option key={t} value={t}>{t.replace("_", " ")}</option>)}
                        </select>
                    </div>
                </div>
                <div style={{ marginBottom: 16 }}>
                    <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, display: "block" }}>Description</label>
                    <input className="input" value={form.description || ""} onChange={(e) => updateField("description", e.target.value)}
                        placeholder="Brief description of what this agent does" />
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <label style={{ fontSize: 13, color: "var(--text-muted)" }}>Active</label>
                    <div className={`toggle-switch ${form.active ? "active" : ""}`}
                        onClick={() => updateField("active", !form.active)} />
                </div>
            </div>

            {/* Greeting + Voice */}
            <div className="glass-card" style={{ padding: 24, marginBottom: 20 }}>
                <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Conversation</h3>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
                    <div>
                        <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, display: "block" }}>Greeting</label>
                        <input className="input" value={form.greeting || ""} onChange={(e) => updateField("greeting", e.target.value)}
                            placeholder="First thing the agent says" />
                    </div>
                    <div>
                        <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, display: "block" }}>Voice</label>
                        <select className="input" value={form.voice_id || "en-US-Chirp3-HD-Charon"}
                            onChange={(e) => updateField("voice_id", e.target.value)}>
                            {VOICE_OPTIONS.map(v => <option key={v.id} value={v.id}>{v.label}</option>)}
                        </select>
                    </div>
                </div>
                <div>
                    <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, display: "block" }}>System Prompt (Persona & Rules)</label>
                    <textarea className="input" value={form.system_prompt || ""} onChange={(e) => updateField("system_prompt", e.target.value)}
                        placeholder="You are a professional receptionist for..."
                        style={{ minHeight: 140 }} />
                </div>
            </div>

            {/* Guardrail Slider */}
            <div className="glass-card" style={{ padding: 24, marginBottom: 20 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                    <h3 style={{ fontSize: 15, fontWeight: 600 }}>Guardrail Level</h3>
                    <span className="badge badge-info">
                        {guardrailLabel(form.guardrail_level ?? 0.5)} — {((form.guardrail_level ?? 0.5) * 100).toFixed(0)}%
                    </span>
                </div>
                <div style={{ position: "relative", marginBottom: 12 }}>
                    <div className="guardrail-track" />
                    <input type="range" min="0" max="100"
                        value={(form.guardrail_level ?? 0.5) * 100}
                        onChange={(e) => updateField("guardrail_level", Number(e.target.value) / 100)}
                        className="guardrail-slider" />
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "var(--text-muted)" }}>
                    <span>Free Talk</span><span>Flexible</span><span>Guided</span><span>Strict Script</span>
                </div>
            </div>

            {/* Limits */}
            <div className="glass-card" style={{ padding: 24, marginBottom: 20 }}>
                <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Call Limits</h3>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                    <div>
                        <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, display: "block" }}>Max Turns</label>
                        <input className="input" type="number" min={1} max={50}
                            value={form.max_turns ?? 20}
                            onChange={(e) => updateField("max_turns", parseInt(e.target.value) || 20)} />
                    </div>
                    <div>
                        <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, display: "block" }}>Max Duration (minutes)</label>
                        <input className="input" type="number" min={1} max={30}
                            value={Math.round((form.max_duration_seconds ?? 300) / 60)}
                            onChange={(e) => updateField("max_duration_seconds", (parseInt(e.target.value) || 5) * 60)} />
                    </div>
                </div>
            </div>

            {/* Tools */}
            <div className="glass-card" style={{ padding: 24, marginBottom: 20 }}>
                <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Tools</h3>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                    {ALL_TOOLS.map((tool) => {
                        const enabled = (form.allowed_tools || []).includes(tool.id);
                        return (
                            <div key={tool.id} onClick={() => toggleTool(tool.id)}
                                style={{
                                    padding: 16, cursor: "pointer", display: "flex", alignItems: "center", gap: 14,
                                    background: enabled ? "rgba(59, 130, 246, 0.08)" : "rgba(15, 20, 25, 0.5)",
                                    border: `1px solid ${enabled ? "rgba(59, 130, 246, 0.3)" : "var(--border)"}`,
                                    borderRadius: 12, transition: "all 0.15s ease",
                                }}>
                                <span style={{ fontSize: 24 }}>{tool.icon}</span>
                                <div style={{ flex: 1 }}>
                                    <div style={{ fontSize: 14, fontWeight: 600, color: enabled ? "var(--text-primary)" : "var(--text-secondary)" }}>{tool.label}</div>
                                    <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{tool.desc}</div>
                                </div>
                                <div className={`toggle-switch ${enabled ? "active" : ""}`} />
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Escalation */}
            <div className="glass-card" style={{ padding: 24, marginBottom: 20 }}>
                <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Escalation Triggers</h3>
                <p style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 12 }}>
                    When a caller says any of these phrases, the agent will offer to transfer to a human.
                </p>
                <input className="input"
                    value={(form.escalation_triggers || []).join(", ")}
                    onChange={(e) => updateField("escalation_triggers", e.target.value.split(",").map(s => s.trim()).filter(Boolean))}
                    placeholder="speak to a human, transfer me, manager (comma separated)" />
            </div>

            {/* State Machine Builder */}
            <div className="glass-card" style={{ padding: 24, marginBottom: 20 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                    <div>
                        <h3 style={{ fontSize: 15, fontWeight: 600 }}>Conversation Flow</h3>
                        <p style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 4 }}>
                            Define the states your agent moves through during a call
                        </p>
                    </div>
                    <button onClick={addState}
                        style={{
                            display: "flex", alignItems: "center", gap: 6, padding: "8px 14px",
                            background: "rgba(59, 130, 246, 0.1)", border: "1px solid rgba(59, 130, 246, 0.3)",
                            borderRadius: 8, color: "#60a5fa", fontSize: 13, fontWeight: 600, cursor: "pointer",
                        }}>
                        <Plus className="w-4 h-4" /> Add State
                    </button>
                </div>

                {/* Visual Flow Preview */}
                <StateFlowPreview states={form.states || []} />

                {/* State Cards */}
                <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 8 }}>
                    {(form.states || []).map((state, i) => (
                        <StateCard
                            key={i}
                            state={state}
                            index={i}
                            allStates={form.states || []}
                            expanded={expandedState === i}
                            onToggle={() => setExpandedState(expandedState === i ? null : i)}
                            onChange={(s) => updateState(i, s)}
                            onDelete={() => deleteState(i)}
                            onMoveUp={() => moveState(i, i - 1)}
                            onMoveDown={() => moveState(i, i + 1)}
                            isFirst={i === 0}
                            isLast={i === (form.states || []).length - 1}
                        />
                    ))}
                </div>

                {(form.states || []).length === 0 && (
                    <div style={{
                        padding: "32px 16px", textAlign: "center", color: "var(--text-muted)",
                        border: "2px dashed var(--border)", borderRadius: 12, marginTop: 8,
                    }}>
                        <p style={{ fontSize: 14, marginBottom: 8 }}>No conversation states defined</p>
                        <p style={{ fontSize: 12 }}>Add states to create a guided conversation flow, or leave empty for free-form conversations.</p>
                    </div>
                )}
            </div>

            {/* Webhook (collapsible) */}
            <details className="glass-card" style={{ padding: 24, marginBottom: 20 }}>
                <summary style={{ fontSize: 15, fontWeight: 600, cursor: "pointer", color: "var(--text-primary)" }}>
                    Webhook Integration (Advanced)
                </summary>
                <div style={{ marginTop: 16 }}>
                    <div style={{ marginBottom: 16 }}>
                        <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, display: "block" }}>Webhook URL</label>
                        <input className="input" value={form.webhook_url || ""}
                            onChange={(e) => updateField("webhook_url", e.target.value || null)}
                            placeholder="https://your-api.com/webhook" />
                    </div>
                    <div>
                        <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, display: "block" }}>Headers (JSON)</label>
                        <textarea className="input"
                            value={JSON.stringify(form.webhook_headers || {}, null, 2)}
                            onChange={(e) => { try { updateField("webhook_headers", JSON.parse(e.target.value)); } catch { } }}
                            placeholder='{"Authorization": "Bearer token"}'
                            style={{ minHeight: 60, fontFamily: "monospace", fontSize: 12 }} />
                    </div>
                </div>
            </details>

            {/* Test Call Modal */}
            <TestCallModal
                isOpen={showTestModal}
                onClose={() => setShowTestModal(false)}
                agentId={agentId}
                agentName={form.name || "Agent"}
            />
        </div>
    );
}
