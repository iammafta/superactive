"use client";

import { useState } from "react";
import { useRouter, useParams } from "next/navigation";
import TestCallModal from "@/components/TestCallModal";

const ALL_TOOLS = [
    { id: "book_appointment", label: "Book Appointment", icon: "📅", desc: "Schedule appointments via calendar" },
    { id: "check_availability", label: "Check Availability", icon: "📋", desc: "Query open time slots" },
    { id: "transfer_to_human", label: "Transfer to Human", icon: "🔄", desc: "Warm transfer to live agent" },
    { id: "send_followup_sms", label: "Send Follow-up SMS", icon: "📱", desc: "Send SMS via Twilio" },
    { id: "log_lead", label: "Log Lead", icon: "📝", desc: "Save lead for follow-up" },
    { id: "lookup_client", label: "Lookup Client", icon: "🔍", desc: "Check returning caller" },
    { id: "call_business_api", label: "Business API", icon: "🌐", desc: "Query custom webhook" },
];

const TEMPLATES = [
    { id: "insurance", label: "Insurance Qualifier", emoji: "🛡️" },
    { id: "medical", label: "Medical Receptionist", emoji: "🏥" },
    { id: "restaurant", label: "Restaurant Host", emoji: "🍽️" },
    { id: "custom", label: "Custom Agent", emoji: "🤖" },
];

function guardrailLabel(level: number): string {
    if (level >= 0.8) return "Strict Script";
    if (level >= 0.5) return "Guided";
    if (level >= 0.2) return "Flexible";
    return "Free Talk";
}

export default function AgentEditorPage() {
    const router = useRouter();
    const params = useParams();
    const agentId = params.id as string;

    const [showTestModal, setShowTestModal] = useState(false);
    const [name, setName] = useState("New Agent");
    const [businessType, setBusinessType] = useState("custom");
    const [guardrail, setGuardrail] = useState(0.5);
    const [greeting, setGreeting] = useState("Hello, how can I help you today?");
    const [systemPrompt, setSystemPrompt] = useState("");
    const [enabledTools, setEnabledTools] = useState<Set<string>>(new Set(["transfer_to_human"]));
    const [escalationTriggers, setEscalationTriggers] = useState("speak to a human, transfer me, manager");

    const toggleTool = (toolId: string) => {
        setEnabledTools((prev) => {
            const next = new Set(prev);
            if (next.has(toolId)) next.delete(toolId);
            else next.add(toolId);
            return next;
        });
    };

    return (
        <div style={{ maxWidth: 900, margin: "0 auto" }}>
            {/* Header */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 28 }}>
                <div>
                    <button
                        onClick={() => router.push("/agents")}
                        style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: 14, marginBottom: 8, padding: 0 }}
                    >
                        ← Back to Agents
                    </button>
                    <h1 style={{ fontSize: 24, fontWeight: 700 }}>Agent Builder</h1>
                </div>
                <div style={{ display: "flex", gap: 12 }}>
                    <button
                        className="btn-primary"
                        style={{ display: "flex", alignItems: "center", gap: 6 }}
                        onClick={() => setShowTestModal(true)}
                    >
                        📞 Test Call
                    </button>
                    <button className="btn-primary">Save Agent</button>
                </div>
            </div>

            {/* Template Selector */}
            <div className="glass-card" style={{ padding: 24, marginBottom: 20 }}>
                <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Start from Template</h3>
                <div style={{ display: "flex", gap: 12 }}>
                    {TEMPLATES.map((t) => (
                        <button
                            key={t.id}
                            onClick={() => setBusinessType(t.id)}
                            style={{
                                flex: 1,
                                padding: "16px 12px",
                                background: businessType === t.id ? "rgba(59, 130, 246, 0.15)" : "rgba(15, 20, 25, 0.6)",
                                border: `1px solid ${businessType === t.id ? "rgba(59, 130, 246, 0.4)" : "var(--border)"}`,
                                borderRadius: 12,
                                cursor: "pointer",
                                textAlign: "center",
                                color: businessType === t.id ? "var(--accent)" : "var(--text-secondary)",
                                transition: "all 0.15s ease",
                            }}
                        >
                            <div style={{ fontSize: 28, marginBottom: 6 }}>{t.emoji}</div>
                            <div style={{ fontSize: 13, fontWeight: 600 }}>{t.label}</div>
                        </button>
                    ))}
                </div>
            </div>

            {/* Basic Info */}
            <div className="glass-card" style={{ padding: 24, marginBottom: 20 }}>
                <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Agent Identity</h3>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
                    <div>
                        <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, display: "block" }}>Agent Name</label>
                        <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Dr. Smith's Receptionist" />
                    </div>
                    <div>
                        <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, display: "block" }}>Greeting</label>
                        <input className="input" value={greeting} onChange={(e) => setGreeting(e.target.value)} placeholder="First thing the agent says" />
                    </div>
                </div>
                <div>
                    <label style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 6, display: "block" }}>System Prompt (Persona & Rules)</label>
                    <textarea
                        className="input"
                        value={systemPrompt}
                        onChange={(e) => setSystemPrompt(e.target.value)}
                        placeholder="You are a professional receptionist for..."
                        style={{ minHeight: 140 }}
                    />
                </div>
            </div>

            {/* Guardrail Slider */}
            <div className="glass-card" style={{ padding: 24, marginBottom: 20 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                    <h3 style={{ fontSize: 15, fontWeight: 600 }}>Guardrail Level</h3>
                    <span className="badge badge-info">{guardrailLabel(guardrail)} — {(guardrail * 100).toFixed(0)}%</span>
                </div>
                <div style={{ position: "relative", marginBottom: 12 }}>
                    <div className="guardrail-track" />
                    <input
                        type="range"
                        min="0"
                        max="100"
                        value={guardrail * 100}
                        onChange={(e) => setGuardrail(Number(e.target.value) / 100)}
                        className="guardrail-slider"
                    />
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "var(--text-muted)" }}>
                    <span>Free Talk</span>
                    <span>Flexible</span>
                    <span>Guided</span>
                    <span>Strict Script</span>
                </div>
                <p style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 12, lineHeight: 1.5 }}>
                    {guardrail < 0.2 && "Agent speaks freely with minimal constraints. Best for general-purpose assistants."}
                    {guardrail >= 0.2 && guardrail < 0.5 && "Agent follows guidelines loosely, can discuss related topics naturally."}
                    {guardrail >= 0.5 && guardrail < 0.8 && "Agent follows the script closely, redirects off-topic questions. Recommended for most businesses."}
                    {guardrail >= 0.8 && "Agent follows the exact script with no deviation. Best for regulated industries."}
                </p>
            </div>

            {/* Tools */}
            <div className="glass-card" style={{ padding: 24, marginBottom: 20 }}>
                <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Tools</h3>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                    {ALL_TOOLS.map((tool) => {
                        const enabled = enabledTools.has(tool.id);
                        return (
                            <div
                                key={tool.id}
                                onClick={() => toggleTool(tool.id)}
                                style={{
                                    padding: "16px",
                                    background: enabled ? "rgba(59, 130, 246, 0.08)" : "rgba(15, 20, 25, 0.5)",
                                    border: `1px solid ${enabled ? "rgba(59, 130, 246, 0.3)" : "var(--border)"}`,
                                    borderRadius: 12,
                                    cursor: "pointer",
                                    display: "flex",
                                    alignItems: "center",
                                    gap: 14,
                                    transition: "all 0.15s ease",
                                }}
                            >
                                <span style={{ fontSize: 24 }}>{tool.icon}</span>
                                <div style={{ flex: 1 }}>
                                    <div style={{ fontSize: 14, fontWeight: 600, color: enabled ? "var(--text-primary)" : "var(--text-secondary)" }}>
                                        {tool.label}
                                    </div>
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
                <input
                    className="input"
                    value={escalationTriggers}
                    onChange={(e) => setEscalationTriggers(e.target.value)}
                    placeholder="speak to a human, transfer me, manager (comma separated)"
                />
            </div>
            {/* Test Call Modal */}
            <TestCallModal
                isOpen={showTestModal}
                onClose={() => setShowTestModal(false)}
                agentId={agentId}
                agentName={name}
            />
        </div>
    );
}
