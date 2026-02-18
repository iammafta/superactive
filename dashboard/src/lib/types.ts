// Shared types matching the backend Pydantic models exactly

export interface StateConfig {
    name: string;
    instructions: string;
    transitions: Record<string, string>;
    max_turns: number;
    required_info: string[];
}

export interface AgentConfig {
    id: string;
    name: string;
    business_type: string;
    system_prompt: string;
    greeting: string;
    voice_id: string;
    guardrail_level: number;
    allowed_tools: string[];
    webhook_url: string | null;
    webhook_headers: Record<string, string>;
    states: StateConfig[];
    max_turns: number;
    max_duration_seconds: number;
    escalation_triggers: string[];
    active: boolean;
    description: string;
}

export interface CallRecord {
    call_id: string;
    agent_id: string;
    business_type: string;
    started_at: string;
    ended_at: string | null;
    duration_seconds: number;
    outcome: "booked" | "transferred" | "completed" | "hung_up" | "in_progress";
    outcome_detail: string;
    states_visited: string[];
    hang_up_state: string | null;
    state_transitions: { from: string; to: string; turn: number }[];
    total_turns: number;
    frustration_triggered: boolean;
    escalation_triggered: boolean;
    repeat_detected: boolean;
    tools_used: string[];
    transcript: { role: string; text: string; ts: string }[];
}

export interface CampaignConfig {
    id: string;
    name: string;
    agent_id: string;
    status: "draft" | "active" | "paused" | "completed";
    contacts: { phone: string; name: string; status: string; [key: string]: string }[];
    total_contacts: number;
    called: number;
    booked: number;
    failed: number;
    schedule: Record<string, any> | null;
    created_at: string;
    updated_at: string;
}

export interface AnalyticsData {
    total_calls: number;
    avg_duration: number;
    booking_rate: number;
    frustration_rate: number;
    outcomes: {
        booked: number;
        transferred: number;
        completed: number;
        hung_up: number;
    };
    agent_performance: {
        agent_id: string;
        business_type: string;
        calls: number;
        conversion_rate: number;
        avg_duration: number;
    }[];
    hang_up_heatmap: Record<string, number>;
    calls_per_day: { date: string; count: number }[];
    changes: {
        total_calls: string;
        avg_duration: string;
        booking_rate: string;
        frustration_rate: string;
    };
}
