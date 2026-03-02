"use client";

import { useState, useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import useSWR from "swr";
import {
    ArrowLeft, Save, Phone, Loader2, Plus, Trash2, ChevronDown,
    ChevronUp, ArrowRight, X, AlertCircle, Settings2,
    User, Bot
} from "lucide-react";
import * as Tabs from "@radix-ui/react-tabs";
import * as Slider from "@radix-ui/react-slider";
import * as Accordion from "@radix-ui/react-accordion";
import { motion, AnimatePresence } from "framer-motion";

import { API_BASE_URL, fetcher, createAgent, updateAgent } from "@/lib/api";
import type { AgentConfig, StateConfig } from "@/lib/types";
import TestChatModal from "@/components/TestChatModal";
import TestCallModal from "@/components/TestCallModal";

const ALL_TOOLS = [
    { id: "book_appointment", label: "Book Appointment", icon: "📅", desc: "Schedule appointments via calendar" },
    { id: "check_availability", label: "Check Availability", icon: "📋", desc: "Query open time slots" },
    { id: "transfer_to_human", label: "Transfer to Human", icon: "🔄", desc: "Warm transfer to live agent" },
    { id: "send_followup_sms", label: "Send Follow-up SMS", icon: "📱", desc: "Send SMS via Telnyx" },
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

const DEFAULT_FORM: Partial<AgentConfig> = {
    name: "",
    business_type: "custom",
    agent_type: "inbound",
    guardrail_level: 0.5,
    frustration_tolerance: 1,
    loop_sensitivity: 2,
    greeting: "Hello, how can I help you today?",
    outbound_greeting: "Hello, this is {{agent.name}} calling for {{contact.name}}.",
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
    webhook_payload_mapping: {},
};

function guardrailLabel(level: number): string {
    if (level >= 0.8) return "Strict Script";
    if (level >= 0.5) return "Guided";
    if (level >= 0.2) return "Flexible";
    return "Free Talk";
}

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

    // Filter out timeout from normal visual transitions, as we handle it natively with the explicit dropdown
    const normalTransitions = Object.entries(state.transitions).filter(([trig]) => trig !== "timeout" && trig !== "fallback");
    const fallbackTarget = state.transitions["timeout"] || state.transitions["fallback"] || "";

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

    const setFallback = (target: string) => {
        const t = { ...state.transitions };
        if (!target) {
            delete t["timeout"];
            delete t["fallback"];
        } else {
            t["timeout"] = target;
        }
        onChange({ ...state, transitions: t });
    };

    const addRequiredInfo = () => {
        onChange({
            ...state,
            required_info: [...(state.required_info || []), { name: "", description: "", type: "string" }]
        });
    };

    const updateRequiredInfo = (idx: number, field: string, value: string) => {
        const reqs = [...(state.required_info || [])];
        reqs[idx] = { ...reqs[idx], [field]: value };
        onChange({ ...state, required_info: reqs });
    };

    const removeRequiredInfo = (idx: number) => {
        const reqs = [...(state.required_info || [])];
        reqs.splice(idx, 1);
        onChange({ ...state, required_info: reqs });
    };

    return (
        <motion.div layout className="bg-gray-800/40 border border-gray-700/50 rounded-xl overflow-hidden mb-3">
            {/* Header */}
            <div
                onClick={onToggle}
                className={`flex items-center gap-3 p-4 cursor-pointer hover:bg-gray-700/20 transition-colors ${expanded ? "border-b border-gray-700/50 bg-gray-700/10" : ""}`}
            >
                <div className="flex flex-col gap-1">
                    {!isFirst && (
                        <button onClick={(e) => { e.stopPropagation(); onMoveUp(); }} className="text-gray-500 hover:text-white transition-colors">
                            <ChevronUp className="w-4 h-4" />
                        </button>
                    )}
                    {!isLast && (
                        <button onClick={(e) => { e.stopPropagation(); onMoveDown(); }} className="text-gray-500 hover:text-white transition-colors">
                            <ChevronDown className="w-4 h-4" />
                        </button>
                    )}
                </div>
                <div className="w-8 h-8 rounded-lg bg-blue-500/10 text-blue-400 font-bold flex items-center justify-center text-sm">
                    {index + 1}
                </div>
                <div className="flex-1">
                    <div className="font-semibold text-gray-100">{state.name || "Unnamed State"}</div>
                    <div className="text-xs text-gray-400 mt-1">
                        {normalTransitions.length} transitions &middot; {state.max_turns} max turns
                        {(state.required_info?.length || 0) > 0 && ` \u00B7 ${state.required_info.length} facts`}
                    </div>
                </div>
                <button onClick={(e) => { e.stopPropagation(); onDelete(); }} className="p-2 text-gray-500 hover:text-red-400 transition-colors rounded-lg hover:bg-red-400/10">
                    <Trash2 className="w-4 h-4" />
                </button>
                <div className="p-2 text-gray-500">
                    {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </div>
            </div>

            {/* Expanded Content */}
            <AnimatePresence>
                {expanded && (
                    <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="p-5 flex flex-col gap-5">
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="text-xs text-gray-400 mb-1.5 block">State Name</label>
                                <input className="w-full bg-gray-900/50 border border-gray-700/50 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500/50 transition-colors"
                                    value={state.name} onChange={(e) => onChange({ ...state, name: e.target.value })}
                                    placeholder="e.g. greeting, qualification" />
                            </div>
                            <div>
                                <label className="text-xs text-gray-400 mb-1.5 block">Max Turns Before Timeout</label>
                                <input className="w-full bg-gray-900/50 border border-gray-700/50 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500/50 transition-colors"
                                    type="number" min={1} max={20} value={state.max_turns}
                                    onChange={(e) => onChange({ ...state, max_turns: parseInt(e.target.value) || 5 })} />
                            </div>
                        </div>

                        <div>
                            <label className="text-xs text-gray-400 mb-1.5 block">Instructions</label>
                            <textarea className="w-full bg-gray-900/50 border border-gray-700/50 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500/50 transition-colors min-h-[80px]"
                                value={state.instructions} onChange={(e) => onChange({ ...state, instructions: e.target.value })}
                                placeholder="What should the agent say and listen for in this specific phase?" />
                        </div>

                        {/* Semantic Info Builder */}
                        <div>
                            <label className="text-xs text-gray-400 mb-2 block flex items-center justify-between">
                                Semantic Data Extraction
                            </label>
                            <div className="flex flex-col gap-2 mb-2">
                                {(state.required_info || []).map((info, idx) => (
                                    <div key={idx} className="flex gap-2 items-start">
                                        <input className="flex-1 bg-gray-900/50 border border-gray-700/50 rounded-lg px-3 py-2 text-sm text-blue-300 font-mono focus:outline-none"
                                            placeholder="Fact Key (e.g. date_of_birth)" value={info.name} onChange={(e) => updateRequiredInfo(idx, "name", e.target.value)} />
                                        <input className="flex-[2] bg-gray-900/50 border border-gray-700/50 rounded-lg px-3 py-2 text-sm text-white focus:outline-none"
                                            placeholder="What exactly to ask for" value={info.description} onChange={(e) => updateRequiredInfo(idx, "description", e.target.value)} />
                                        <select className="w-28 bg-gray-900/50 border border-gray-700/50 rounded-lg px-2 py-2 text-sm text-gray-300 focus:outline-none"
                                            value={info.type || "string"} onChange={(e) => updateRequiredInfo(idx, "type", e.target.value)}>
                                            <option value="string">String</option>
                                            <option value="number">Number</option>
                                            <option value="date">Date</option>
                                            <option value="boolean">Boolean</option>
                                        </select>
                                        <button onClick={() => removeRequiredInfo(idx)} className="p-2.5 text-gray-500 hover:text-red-400 transition-colors bg-gray-900/50 rounded-lg border border-gray-700/50 hover:border-red-400/50">
                                            <Trash2 className="w-4 h-4" />
                                        </button>
                                    </div>
                                ))}
                            </div>
                            <button onClick={addRequiredInfo} className="flex items-center gap-2 text-xs text-blue-400 hover:text-blue-300 font-medium py-1">
                                <Plus className="w-3 h-3" /> Add fact to extract
                            </button>
                        </div>

                        {/* Transitions */}
                        <div className="bg-gray-900/30 p-4 rounded-xl border border-gray-800">
                            <label className="text-sm font-semibold text-gray-200 mb-3 block flex items-center gap-2">
                                State Transitions
                            </label>

                            {/* Standard Conditions */}
                            <div className="flex flex-col gap-3 mb-4">
                                {normalTransitions.map(([trigger, target]) => (
                                    <div key={trigger} className="flex items-center gap-3">
                                        <input className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500/50"
                                            value={trigger} placeholder="LLM intent condition"
                                            onChange={(e) => updateTransition(e.target.value, target, trigger)} />
                                        <ArrowRight className="w-4 h-4 text-gray-500 shrink-0" />
                                        <select className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500/50"
                                            value={target} onChange={(e) => updateTransition(trigger, e.target.value)}>
                                            <option value="">Select destination...</option>
                                            {allStates.map((s) => <option key={s.name} value={s.name}>{s.name}</option>)}
                                        </select>
                                        <button onClick={() => removeTransition(trigger)} className="p-2 text-gray-500 hover:text-red-400 transition-colors">
                                            <X className="w-4 h-4" />
                                        </button>
                                    </div>
                                ))}
                                <button onClick={addTransition} className="flex items-center gap-2 text-sm text-blue-400 hover:text-blue-300 font-medium py-2 rounded-lg bg-blue-500/10 hover:bg-blue-500/20 w-fit px-4 transition-colors">
                                    <Plus className="w-4 h-4" /> Add Condition
                                </button>
                            </div>

                            {/* Explicit Fallback/Timeout */}
                            <div className="mt-4 pt-4 border-t border-gray-700/50 flex items-center gap-3">
                                <div className="flex-1">
                                    <h4 className="text-sm font-medium text-amber-200/80 mb-1">Timeout Fallback</h4>
                                    <p className="text-xs text-gray-500">Destination if caller reaches max turns or provides unintelligible answers.</p>
                                </div>
                                <select className="flex-1 bg-gray-900 border border-amber-900/50 text-amber-100 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-amber-500/50"
                                    value={fallbackTarget} onChange={(e) => setFallback(e.target.value)}>
                                    <option value="">No fallback (End call)</option>
                                    {allStates.map((s) => <option key={s.name} value={s.name}>{s.name}</option>)}
                                </select>
                            </div>
                        </div>

                    </motion.div>
                )}
            </AnimatePresence>
        </motion.div>
    );
}

// ── Visual Flow Preview ──────────────────────────────────────────

function StateFlowPreview({ states }: { states: StateConfig[] }) {
    if (states.length === 0) return null;
    return (
        <div className="flex items-center gap-2 flex-wrap py-2">
            {states.map((state, i) => (
                <div key={state.name || i} className="flex items-center gap-2">
                    <div className={`px-3 py-1.5 rounded-lg text-xs font-semibold border ${i === 0 ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400" : "bg-blue-500/10 border-blue-500/20 text-blue-400"}`}>
                        {state.name || `State ${i + 1}`}
                    </div>
                    {i < states.length - 1 && <ArrowRight className="w-3.5 h-3.5 text-gray-600" />}
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
        fetcher,
        {
            onSuccess: (data) => {
                if (data.states?.length > 0 && paradigm === "free") setParadigm("structured");
            }
        }
    );

    const [form, setForm] = useState<Partial<AgentConfig>>({ ...DEFAULT_FORM });
    const [webhookHeadersStr, setWebhookHeadersStr] = useState("{}");
    const [saving, setSaving] = useState(false);
    const [saveError, setSaveError] = useState("");
    const [showTestModal, setShowTestModal] = useState(false);
    const [showTelephonyModal, setShowTelephonyModal] = useState(false);
    const [expandedState, setExpandedState] = useState<number | null>(null);

    // Paradigm control (Free vs Structured)
    const [paradigm, setParadigm] = useState<"free" | "structured">("structured");

    useEffect(() => {
        if (existingAgent) {
            setForm(existingAgent);
            setWebhookHeadersStr(JSON.stringify(existingAgent.webhook_headers || {}, null, 2));
            if ((existingAgent.states?.length || 0) === 0) {
                setParadigm("free");
            }
        }
    }, [existingAgent]);

    const updateField = <K extends keyof AgentConfig>(key: K, value: AgentConfig[K]) => {
        setForm((prev) => ({ ...prev, [key]: value }));
    };

    const toggleTool = (toolId: string) => {
        const current = form.allowed_tools || [];
        if (current.includes(toolId)) updateField("allowed_tools", current.filter(t => t !== toolId));
        else updateField("allowed_tools", [...current, toolId]);
    };

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
            const payload = { ...form, tenant_id: "" };
            // If user toggled back to free-flowing, we wipe states to ensure true statelessness
            if (paradigm === "free") {
                payload.states = [];
            }

            if (isNew) {
                delete payload.id;
                await createAgent(payload);
            } else {
                payload.id = agentId;
                await updateAgent(agentId, payload);
            }
            router.push("/agents");
        } catch (err: unknown) {
            setSaveError((err as Error).message || "Failed to save");
        } finally {
            setSaving(false);
        }
    };

    if (!isNew && isLoading) return (
        <div className="flex items-center justify-center h-screen text-gray-400 gap-3">
            <Loader2 className="w-6 h-6 animate-spin text-blue-500" />Loading system architecture...
        </div>
    );

    if (!isNew && error) return (
        <div className="p-12 text-center text-red-400">
            <AlertCircle className="w-8 h-8 mx-auto mb-2" />Failed to establish agent feed: {error.message}
        </div>
    );

    return (
        <div className="max-w-[1000px] w-full pb-32">

            {/* Header Area */}
            <div className="sticky top-0 z-10 bg-[#0B0F19]/80 backdrop-blur-xl border-b border-gray-800/60 pb-4 pt-4 mb-8 -mx-8 px-8">
                <div className="flex justify-between items-center max-w-[1000px] mx-auto">
                    <div>
                        <button onClick={() => router.push("/agents")} className="flex items-center gap-2 text-sm text-gray-400 hover:text-white transition-colors mb-2">
                            <ArrowLeft className="w-4 h-4" /> Return to Fleet
                        </button>
                        <h1 className="text-2xl font-bold text-white tracking-tight">{isNew ? "Create Agent" : `Edit: ${form.name}`}</h1>
                        {!isNew && <p className="text-xs text-gray-500 font-mono mt-1">ID: {agentId}</p>}
                    </div>
                    <div className="flex gap-3">
                        {!isNew && (
                            <>
                                <button onClick={() => setShowTestModal(true)} className="flex items-center gap-2 px-4 py-2 bg-blue-500/10 text-blue-400 border border-blue-500/20 rounded-lg text-sm font-semibold hover:bg-blue-500/20 transition-all">
                                    <Bot className="w-4 h-4" /> Simulate Chat
                                </button>
                                <button onClick={() => setShowTelephonyModal(true)} className="flex items-center gap-2 px-4 py-2 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded-lg text-sm font-semibold hover:bg-emerald-500/20 transition-all">
                                    <Phone className="w-4 h-4" /> Test Call
                                </button>
                            </>
                        )}
                        <button onClick={handleSave} disabled={saving} className="flex items-center gap-2 px-5 py-2 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-500 transition-all disabled:opacity-50 shadow-lg shadow-blue-500/20">
                            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                            {saving ? "Compiling..." : (isNew ? "Initialize Protocol" : "Deploy Changes")}
                        </button>
                    </div>
                </div>
            </div>

            {saveError && (
                <div className="flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm mb-6">
                    <AlertCircle className="w-4 h-4" /> {saveError}
                </div>
            )}

            {/* Core Topology */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                <div className="md:col-span-2 bg-gray-900/50 border border-gray-800 rounded-2xl p-6 backdrop-blur-md">
                    <h3 className="text-sm font-bold tracking-wider text-gray-400 uppercase mb-5">Primary Identity</h3>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-5">
                        <div className="md:col-span-1">
                            <label className="text-xs text-gray-400 mb-1.5 block">Callsign (Agent Name)</label>
                            <input className="w-full bg-gray-950 border border-gray-800 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500/50 transition-colors"
                                value={form.name || ""} onChange={(e) => updateField("name", e.target.value)} placeholder="e.g. Atlas Medical" />
                        </div>
                        <div className="md:col-span-1">
                            <label className="text-xs text-gray-400 mb-1.5 block">Agent Direction</label>
                            <select className="w-full bg-gray-950 border border-gray-800 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500/50 transition-colors"
                                value={form.agent_type || "inbound"} onChange={(e) => updateField("agent_type", e.target.value as "inbound" | "outbound" | "hybrid")}>
                                <option value="inbound">Inbound Responder</option>
                                <option value="outbound">Outbound Dialer</option>
                                <option value="hybrid">Hybrid (Both)</option>
                            </select>
                        </div>
                        <div className="md:col-span-1">
                            <label className="text-xs text-gray-400 mb-1.5 block">Vertical Array</label>
                            <select className="w-full bg-gray-950 border border-gray-800 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500/50 transition-colors"
                                value={form.business_type || "custom"} onChange={(e) => updateField("business_type", e.target.value)}>
                                {BUSINESS_TYPES.map(t => <option key={t} value={t}>{t.replace("_", " ").toUpperCase()}</option>)}
                            </select>
                        </div>
                    </div>
                    <div className="mb-5">
                        <label className="text-xs text-gray-400 mb-1.5 block">Operational Directive (Description)</label>
                        <input className="w-full bg-gray-950 border border-gray-800 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500/50 transition-colors"
                            value={form.description || ""} onChange={(e) => updateField("description", e.target.value)} placeholder="Brief description of what this agent accomplishes" />
                    </div>
                </div>

                <div className="bg-gradient-to-br from-blue-900/20 to-purple-900/10 border border-blue-900/30 rounded-2xl p-6 flex flex-col justify-center items-center">
                    <h3 className="text-sm font-bold tracking-wider text-gray-400 uppercase mb-5 w-full text-center">Status Control</h3>
                    <div className={`w-16 h-8 rounded-full cursor-pointer relative transition-colors ${form.active ? "bg-blue-500/40 border border-blue-400/50" : "bg-gray-800 border border-gray-700"}`} onClick={() => updateField("active", !form.active)}>
                        <motion.div layout className={`absolute top-1 w-6 h-6 rounded-full ${form.active ? "bg-blue-400" : "bg-gray-500"}`} style={{ [form.active ? "right" : "left"]: 4 }} />
                    </div>
                    <p className="text-xs text-gray-400 mt-4 text-center">
                        {form.active ? "Agent is currently accepting telephony requests." : "Agent is offline and will reject inbound calls."}
                    </p>
                </div>
            </div>

            {/* Interactive Linguistics */}
            <div className="bg-gray-900/50 border border-gray-800 rounded-2xl p-6 backdrop-blur-md mb-6">
                <div className="flex justify-between items-center mb-6">
                    <h3 className="text-sm font-bold tracking-wider text-gray-400 uppercase">Interactive Linguistics</h3>
                    <div className="flex items-center gap-3 bg-gray-950 p-1.5 rounded-lg border border-gray-800">
                        <User className="w-4 h-4 text-gray-500 ml-2" />
                        <select className="bg-transparent text-sm text-gray-200 outline-none pr-4 font-medium" value={form.voice_id || "en-US-Chirp3-HD-Charon"} onChange={(e) => updateField("voice_id", e.target.value)}>
                            {VOICE_OPTIONS.map(v => <option key={v.id} value={v.id}>{v.label}</option>)}
                        </select>
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                        <label className="text-xs text-gray-400 mb-2 block">System Prompt / Persona</label>
                        <textarea className="w-full bg-gray-950 border border-gray-800 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-blue-500/50 min-h-[160px] leading-relaxed shadow-inner"
                            value={form.system_prompt || ""} onChange={(e) => updateField("system_prompt", e.target.value)} placeholder="You are a warm, fast-paced expert..." />
                    </div>
                    <div>
                        <Tabs.Root defaultValue="inbound" className="w-full flex flex-col h-full">
                            <Tabs.List className="flex border-b border-gray-800 mb-4 h-10">
                                <Tabs.Trigger value="inbound" className="px-4 py-2 text-sm font-medium text-gray-500 data-[state=active]:text-blue-400 data-[state=active]:border-b-2 data-[state=active]:border-blue-400 transition-colors">
                                    Inbound (Default)
                                </Tabs.Trigger>
                                <Tabs.Trigger value="outbound" className="px-4 py-2 text-sm font-medium text-gray-500 data-[state=active]:text-emerald-400 data-[state=active]:border-b-2 data-[state=active]:border-emerald-400 transition-colors">
                                    Outbound Campaign
                                </Tabs.Trigger>
                            </Tabs.List>
                            <Tabs.Content value="inbound" className="flex-1 outline-none">
                                <p className="text-xs text-gray-500 mb-3">The very first thing the agent says when a user calls them.</p>
                                <textarea className="w-full bg-gray-950 border border-gray-800 rounded-xl px-4 py-3 text-sm text-blue-200 focus:outline-none focus:border-blue-500/50 min-h-[90px] font-medium"
                                    value={form.greeting || ""} onChange={(e) => updateField("greeting", e.target.value)} placeholder="Hello, Superactive! How can I help?" />
                            </Tabs.Content>
                            <Tabs.Content value="outbound" className="flex-1 outline-none">
                                <p className="text-xs text-gray-500 mb-3">Template for outgoing calls. Use variables like <code className="text-emerald-300 bg-emerald-900/30 px-1 rounded">{"{{contact.name}}"}</code>.</p>
                                <textarea className="w-full bg-gray-950 border border-emerald-900/30 rounded-xl px-4 py-3 text-sm text-emerald-200 focus:outline-none focus:border-emerald-500/50 min-h-[90px] font-medium"
                                    value={form.outbound_greeting || ""} onChange={(e) => updateField("outbound_greeting", e.target.value)} placeholder="Hi {{contact.name}}, this is {{agent.name}} calling from..." />
                            </Tabs.Content>
                        </Tabs.Root>
                    </div>
                </div>
            </div>

            {/* Conversation Flow Paradigm */}
            <div className="bg-gray-900/50 border border-gray-800 rounded-2xl p-6 backdrop-blur-md mb-6 overflow-hidden">
                <div className="flex justify-between items-center mb-6">
                    <h3 className="text-sm font-bold tracking-wider text-gray-400 uppercase">Architecture Paradigm</h3>
                    <div className="flex p-1 bg-gray-950 border border-gray-800 rounded-xl max-w-sm">
                        <button onClick={() => setParadigm("free")} className={`flex-1 flex items-center justify-center gap-2 py-2 px-4 rounded-lg text-sm font-semibold transition-all ${paradigm === "free" ? "bg-gray-800 text-white shadow-md shadow-black/20" : "text-gray-500 hover:text-gray-300"}`}>
                            Free-Flowing
                        </button>
                        <button onClick={() => setParadigm("structured")} className={`flex-1 flex items-center justify-center gap-2 py-2 px-4 rounded-lg text-sm font-semibold transition-all ${paradigm === "structured" ? "bg-blue-600/20 text-blue-400 border border-blue-500/20 shadow-md shadow-blue-900/20" : "text-gray-500 hover:text-gray-300"}`}>
                            Structured State
                        </button>
                    </div>
                </div>

                <AnimatePresence mode="wait">
                    {paradigm === "free" ? (
                        <motion.div key="free" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} className="py-8 text-center bg-gray-950/50 rounded-xl border border-dashed border-gray-800">
                            <Bot className="w-12 h-12 text-gray-600 mx-auto mb-4" />
                            <h4 className="text-white font-semibold mb-2">Stateless Conversational AI</h4>
                            <p className="text-sm text-gray-500 max-w-sm mx-auto">The agent will operate autonomously using only its System Prompt and standard RAG memories to progress the conversation fluidly.</p>
                        </motion.div>
                    ) : (
                        <motion.div key="structured" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} className="flex flex-col gap-4">
                            <div className="flex justify-between items-end mb-2">
                                <p className="text-sm text-gray-400 max-w-md">Design strict transitional states ensuring the agent extracts vital information before moving through the call funnel.</p>
                                <button onClick={addState} className="flex items-center gap-2 px-4 py-2 bg-blue-500/10 text-blue-400 border border-blue-500/20 rounded-lg text-sm font-semibold hover:bg-blue-500/20 transition-all">
                                    <Plus className="w-4 h-4" /> Inject New State
                                </button>
                            </div>

                            {/* Visual Map */}
                            <StateFlowPreview states={form.states || []} />

                            <div className="mt-4">
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
                                {(form.states || []).length === 0 && (
                                    <div className="py-12 text-center text-gray-500 border border-gray-800 border-dashed rounded-xl">
                                        No states injected into sequence loop.
                                    </div>
                                )}
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>

            {/* Hardware / Tool Chain */}
            <div className="bg-gray-900/50 border border-gray-800 rounded-2xl p-6 backdrop-blur-md mb-6">
                <div className="mb-6">
                    <h3 className="text-sm font-bold tracking-wider text-gray-400 uppercase">Tool Chain Payload</h3>
                    <p className="text-xs text-gray-500 mt-1">Capabilities available to the LLM during execution.</p>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    {ALL_TOOLS.map((tool) => {
                        const enabled = (form.allowed_tools || []).includes(tool.id);
                        return (
                            <div key={tool.id} onClick={() => toggleTool(tool.id)} className={`p-4 rounded-xl cursor-pointer border transition-all ${enabled ? "bg-blue-900/20 border-blue-500/40 shadow-inner shadow-blue-500/10" : "bg-gray-950 border-gray-800 hover:border-gray-700"}`}>
                                <div className="text-2xl mb-2">{tool.icon}</div>
                                <div className={`text-sm font-semibold mb-1 ${enabled ? "text-blue-100" : "text-gray-400"}`}>{tool.label}</div>
                                <div className="text-xs text-gray-500 leading-snug">{tool.desc}</div>
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Advanced Tuning Accordion */}
            <Accordion.Root type="single" collapsible className="bg-gray-900/50 border border-gray-800 rounded-2xl overflow-hidden mb-6 backdrop-blur-md">
                <Accordion.Item value="advanced">
                    <Accordion.Header>
                        <Accordion.Trigger className="flex justify-between items-center w-full p-6 group focus:outline-none">
                            <div className="flex items-center gap-3">
                                <Settings2 className="w-5 h-5 text-gray-500 group-hover:text-blue-400 transition-colors" />
                                <h3 className="text-sm font-bold tracking-wider text-gray-400 group-hover:text-blue-400 uppercase transition-colors">Advanced Runtime Tuning</h3>
                            </div>
                            <ChevronDown className="w-5 h-5 text-gray-500 transition-transform duration-300 ease-[cubic-bezier(0.87,_0,_0.13,_1)] group-data-[state=open]:rotate-180" />
                        </Accordion.Trigger>
                    </Accordion.Header>
                    <Accordion.Content className="overflow-hidden data-[state=closed]:animate-slideUp data-[state=open]:animate-slideDown">
                        <div className="p-6 pt-0 border-t border-gray-800/50 mt-2 grid grid-cols-1 md:grid-cols-3 gap-8">

                            <div className="flex flex-col gap-4">
                                <div>
                                    <div className="flex justify-between items-end mb-2">
                                        <label className="text-xs font-semibold text-gray-300">Guardrail Confinement</label>
                                        <span className="text-[10px] uppercase font-bold text-blue-400 px-2 py-0.5 bg-blue-500/10 rounded">{guardrailLabel(form.guardrail_level ?? 0.5)}</span>
                                    </div>
                                    <Slider.Root className="relative flex items-center w-full h-5 cursor-pointer touch-none" value={[(form.guardrail_level ?? 0.5) * 100]} max={100} step={1} onValueChange={(v) => updateField("guardrail_level", v[0] / 100)}>
                                        <Slider.Track className="bg-gray-800 relative grow rounded-full h-1.5">
                                            <Slider.Range className="absolute bg-blue-500 rounded-full h-full" />
                                        </Slider.Track>
                                        <Slider.Thumb className="block w-4 h-4 bg-white rounded-full shadow-[0_2px_10px] shadow-blackA4 hover:bg-violet3 focus:outline-none focus:shadow-[0_0_0_5px] focus:shadow-blackA8" />
                                    </Slider.Root>
                                    <p className="text-xs text-gray-600 mt-2">Strictness against off-topic drift.</p>
                                </div>
                            </div>

                            <div className="flex flex-col gap-4">
                                <div>
                                    <div className="flex justify-between items-end mb-2">
                                        <label className="text-xs font-semibold text-gray-300">Frustration Tolerance</label>
                                        <span className="text-[10px] uppercase font-bold text-red-400 px-2 py-0.5 bg-red-500/10 rounded">{form.frustration_tolerance ?? 1} triggers</span>
                                    </div>
                                    <Slider.Root className="relative flex items-center w-full h-5 cursor-pointer touch-none" value={[form.frustration_tolerance ?? 1]} min={1} max={5} step={1} onValueChange={(v) => updateField("frustration_tolerance", v[0])}>
                                        <Slider.Track className="bg-gray-800 relative grow rounded-full h-1.5">
                                            <Slider.Range className="absolute bg-red-500 rounded-full h-full" />
                                        </Slider.Track>
                                        <Slider.Thumb className="block w-4 h-4 bg-white rounded-full shadow-lg hover:scale-110 focus:outline-none transition-transform" />
                                    </Slider.Root>
                                    <p className="text-xs text-gray-600 mt-2">Phrases like &quot;speak to human&quot; before escalation.</p>
                                </div>
                            </div>

                            <div className="flex flex-col gap-4">
                                <div>
                                    <div className="flex justify-between items-end mb-2">
                                        <label className="text-xs font-semibold text-gray-300">Loop Sensitivity</label>
                                        <span className="text-[10px] uppercase font-bold text-amber-400 px-2 py-0.5 bg-amber-500/10 rounded">{form.loop_sensitivity ?? 2} turns</span>
                                    </div>
                                    <Slider.Root className="relative flex items-center w-full h-5 cursor-pointer touch-none" value={[form.loop_sensitivity ?? 2]} min={1} max={5} step={1} onValueChange={(v) => updateField("loop_sensitivity", v[0])}>
                                        <Slider.Track className="bg-gray-800 relative grow rounded-full h-1.5">
                                            <Slider.Range className="absolute bg-amber-500 rounded-full h-full" />
                                        </Slider.Track>
                                        <Slider.Thumb className="block w-4 h-4 bg-white rounded-full shadow-lg hover:scale-110 focus:outline-none transition-transform" />
                                    </Slider.Root>
                                    <p className="text-xs text-gray-600 mt-2">Repeated questions until forcing state advancement.</p>
                                </div>
                            </div>

                            <div className="col-span-full">
                                <label className="text-xs text-gray-400 mb-1.5 block">Escalation Trigger Phrases (Comma separated)</label>
                                <input className="w-full bg-gray-950 border border-gray-800 rounded-lg px-4 py-2.5 text-sm text-gray-300 focus:outline-none focus:border-red-500/50"
                                    value={(form.escalation_triggers || []).join(", ")} onChange={(e) => updateField("escalation_triggers", e.target.value.split(",").map(s => s.trim()).filter(Boolean))} />
                            </div>

                        </div>
                    </Accordion.Content>
                </Accordion.Item>
            </Accordion.Root>

            {/* Webhook Mapper */}
            <Accordion.Root type="single" collapsible className="bg-gray-900/50 border border-gray-800 rounded-2xl overflow-hidden mb-6 backdrop-blur-md">
                <Accordion.Item value="webhook">
                    <Accordion.Header>
                        <Accordion.Trigger className="flex justify-between items-center w-full p-6 group focus:outline-none">
                            <div className="flex flex-col items-start gap-1">
                                <h3 className="text-sm font-bold tracking-wider text-gray-400 group-hover:text-fuchsia-400 uppercase transition-colors">Enterprise Webhook Bus</h3>
                                <p className="text-xs text-gray-500">Export call artifacts to CRMs (Zapier, Salesforce) seamlessly upon termination.</p>
                            </div>
                            <ChevronDown className="w-5 h-5 text-gray-500 transition-transform duration-300 ease-[cubic-bezier(0.87,_0,_0.13,_1)] group-data-[state=open]:rotate-180" />
                        </Accordion.Trigger>
                    </Accordion.Header>
                    <Accordion.Content className="overflow-hidden data-[state=closed]:animate-slideUp data-[state=open]:animate-slideDown">
                        <div className="p-6 pt-0 border-t border-gray-800/50 mt-4 flex flex-col gap-6">

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <div>
                                    <label className="text-xs text-gray-400 mb-1.5 block">Endpoint URL</label>
                                    <input className="w-full bg-gray-950 border border-gray-800 rounded-lg px-4 py-2.5 text-sm font-mono text-fuchsia-200 focus:outline-none focus:border-fuchsia-500/50 transition-colors"
                                        value={form.webhook_url || ""} onChange={(e) => updateField("webhook_url", e.target.value || null)} placeholder="https://hooks.zapier.com/..." />
                                </div>
                                <div>
                                    <label className="text-xs text-gray-400 mb-1.5 block">Authorization Headers (JSON)</label>
                                    <input className="w-full bg-gray-950 border border-gray-800 rounded-lg px-4 py-2.5 text-sm font-mono text-gray-400 focus:outline-none focus:border-fuchsia-500/50 transition-colors"
                                        value={webhookHeadersStr}
                                        onChange={(e) => setWebhookHeadersStr(e.target.value)}
                                        onBlur={() => { try { const p = JSON.parse(webhookHeadersStr); updateField("webhook_headers", p); setWebhookHeadersStr(JSON.stringify(p)); } catch { } }}
                                        placeholder='{"Authorization": "Bearer token"}' />
                                </div>
                            </div>

                            <div className="bg-gray-950/50 p-4 rounded-xl border border-dashed border-gray-800">
                                <label className="text-xs font-semibold text-gray-300 mb-3 block">Payload Mapping Strategy</label>
                                <p className="text-xs text-gray-500 mb-4">Map internal Semantic Facts to custom JSON keys your CRM expects.</p>

                                <div className="flex flex-col gap-3">
                                    {Object.entries(form.webhook_payload_mapping || {}).map(([internalKey, externalKey], idx) => (
                                        <div key={idx} className="flex gap-3 items-center">
                                            <input className="flex-1 bg-gray-900 border border-gray-700/50 rounded-lg px-3 py-2 text-sm text-blue-300 font-mono focus:outline-none"
                                                value={internalKey} readOnly disabled />
                                            <ArrowRight className="w-4 h-4 text-gray-600 shrink-0" />
                                            <input className="flex-1 bg-gray-900 border border-gray-700/50 rounded-lg px-3 py-2 text-sm text-fuchsia-300 font-mono focus:outline-none border-fuchsia-900/30"
                                                value={externalKey} onChange={(e) => {
                                                    const m = { ...form.webhook_payload_mapping };
                                                    m[internalKey] = e.target.value;
                                                    updateField("webhook_payload_mapping", m);
                                                }} />
                                            <button onClick={() => {
                                                const m = { ...form.webhook_payload_mapping };
                                                delete m[internalKey];
                                                updateField("webhook_payload_mapping", m);
                                            }} className="p-2 text-gray-500 hover:text-red-400 transition-colors">
                                                <X className="w-4 h-4" />
                                            </button>
                                        </div>
                                    ))}
                                    <div className="flex gap-3 items-center mt-2">
                                        <input id="newMappingKey" placeholder="Internal Fact (e.g. date_of_birth)" className="flex-1 bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-sm text-gray-300 font-mono focus:outline-none" />
                                        <ArrowRight className="w-4 h-4 text-gray-700 shrink-0" />
                                        <input id="newMappingVal" placeholder="CRM Key" className="flex-1 bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-sm text-gray-300 font-mono focus:outline-none"
                                            onKeyDown={(e) => {
                                                if (e.key === 'Enter') {
                                                    const keyInput = document.getElementById("newMappingKey") as HTMLInputElement;
                                                    const valInput = document.getElementById("newMappingVal") as HTMLInputElement;
                                                    if (keyInput.value && valInput.value) {
                                                        updateField("webhook_payload_mapping", { ...form.webhook_payload_mapping, [keyInput.value]: valInput.value });
                                                        keyInput.value = ""; valInput.value = "";
                                                    }
                                                }
                                            }} />
                                        <button onClick={() => {
                                            const keyInput = document.getElementById("newMappingKey") as HTMLInputElement;
                                            const valInput = document.getElementById("newMappingVal") as HTMLInputElement;
                                            if (keyInput.value && valInput.value) {
                                                updateField("webhook_payload_mapping", { ...form.webhook_payload_mapping, [keyInput.value]: valInput.value });
                                                keyInput.value = ""; valInput.value = "";
                                            }
                                        }} className="p-2 bg-gray-800 rounded-lg text-white hover:bg-gray-700 transition-colors">
                                            <Plus className="w-4 h-4" />
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </Accordion.Content>
                </Accordion.Item>
            </Accordion.Root>

            <TestChatModal isOpen={showTestModal} onClose={() => setShowTestModal(false)} agentId={agentId} agentName={form.name || "Agent"} />
            <TestCallModal isOpen={showTelephonyModal} onClose={() => setShowTelephonyModal(false)} agentId={agentId} agentName={form.name || "Agent"} />
        </div>
    );
}
