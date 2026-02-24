"use client";

import { useState, useRef } from "react";
import useSWR from "swr";
import { Trash2, Plus, Upload, FileText, Play, Pause, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import {
    API_BASE_URL, fetcher,
    createCampaign, uploadContacts,
    startCampaign, pauseCampaign, resumeCampaign, deleteCampaign, resetCampaign
} from "@/lib/api";
import type { CampaignConfig } from "@/lib/types";
import PageHeader from "@/components/ui/PageHeader";
import Modal from "@/components/ui/Modal";

import EmptyState from "@/components/ui/EmptyState";
import { PhoneOutgoing } from "lucide-react";

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
            toast.error("Please fill in all fields and upload a CSV file.");
            return;
        }

        try {
            setIsCreating(true);

            // Let the backend generate a proper UUID
            const result = await createCampaign({
                name: newCampaignName,
                agent_id: selectedAgentId,
                status: "draft",
                contacts: [],
            });

            // Upload contacts using the server-generated ID
            const campaignId = result?.id || result?.campaign_id;
            if (campaignId && contactFile) {
                await uploadContacts(campaignId, contactFile);
            }

            // Cleanup
            setShowNewCampaign(false);
            setNewCampaignName("");
            setSelectedAgentId("");
            setContactFile(null);
            mutateCampaigns();
            toast.success("Campaign created successfully!");
        } catch (err: unknown) {
            toast.error(`Failed to create campaign: ${(err as Error).message}`);
        } finally {
            setIsCreating(false);
        }
    };

    const handleStart = async (id: string, e: React.MouseEvent) => {
        e.stopPropagation();
        try { await startCampaign(id); mutateCampaigns(); toast.success("Campaign started!"); } catch (err: unknown) { toast.error(`Failed to start: ${(err as Error).message}`); }
    };

    const handlePause = async (id: string, e: React.MouseEvent) => {
        e.stopPropagation();
        try { await pauseCampaign(id); mutateCampaigns(); toast.success("Campaign paused."); } catch (err: unknown) { toast.error(`Failed to pause: ${(err as Error).message}`); }
    };

    const handleResume = async (id: string, e: React.MouseEvent) => {
        e.stopPropagation();
        try { await resumeCampaign(id); mutateCampaigns(); toast.success("Campaign resumed!"); } catch (err: unknown) { toast.error(`Failed to resume: ${(err as Error).message}`); }
    };

    const handleDelete = async (id: string, e: React.MouseEvent) => {
        e.stopPropagation();
        if (!confirm("Are you sure you want to delete this campaign?")) return;
        try { await deleteCampaign(id); mutateCampaigns(); toast.success("Campaign deleted."); } catch (err: unknown) { toast.error(`Failed to delete: ${(err as Error).message}`); }
    };

    const handleReset = async (id: string, e: React.MouseEvent) => {
        e.stopPropagation();
        try { await resetCampaign(id); mutateCampaigns(); toast.success("Campaign reset."); } catch (err: unknown) { toast.error(`Failed to reset: ${(err as Error).message}`); }
    };

    const isLoading = !campaigns && !campaignsError;
    const hasCampaigns = campaigns && campaigns.length > 0;

    return (
        <div>
            {/* Header */}
            <PageHeader
                title="Campaigns"
                description="Outbound calling campaigns — your AI makes the calls"
                action={
                    hasCampaigns && (
                        <button className="btn-primary flex items-center gap-2" onClick={() => setShowNewCampaign(true)}>
                            <Plus className="w-5 h-5" /> New Campaign
                        </button>
                    )
                }
            />

            {/* Loading / Error States */}
            {isLoading && <div className="p-5 text-[var(--text-muted)]">Loading campaigns...</div>}
            {campaignsError && <div className="p-5 text-red-400">Failed to load campaigns. Is the backend running?</div>}

            {/* Campaign Cards or Empty State */}
            {!isLoading && !campaignsError && !hasCampaigns ? (
                <EmptyState
                    icon={PhoneOutgoing}
                    title="No campaigns yet"
                    description="Upload a CSV of contacts and launch an outbound, AI-driven calling campaign."
                    action={
                        <button className="btn-primary flex items-center gap-2" onClick={() => setShowNewCampaign(true)}>
                            <Plus className="w-5 h-5" /> Create Campaign
                        </button>
                    }
                />
            ) : (
                <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
                    {campaigns?.map((campaign) => {
                        const pct = campaign.total_contacts > 0
                            ? Math.round((campaign.called / campaign.total_contacts) * 100)
                            : 0;
                        const convRate = campaign.called > 0
                            ? Math.round((campaign.booked / campaign.called) * 100)
                            : 0;

                        return (
                            <div key={campaign.id} className="glass-card p-6 relative">
                                {/* Delete button (top right) */}
                                <button
                                    onClick={(e) => handleDelete(campaign.id, e)}
                                    className="absolute top-4 right-4 bg-transparent border-none cursor-pointer text-[var(--text-muted)] hover:text-red-400 transition-colors"
                                    title="Delete Campaign"
                                >
                                    <Trash2 className="w-4 h-4" />
                                </button>

                                <div className="flex justify-between items-start mb-4 pr-6">
                                    <div>
                                        <div className="text-base font-semibold text-[var(--text-primary)] mb-1">
                                            {campaign.name}
                                        </div>
                                        <div className="text-xs text-[var(--text-muted)] capitalize">
                                            Agent: {agents?.find(a => a.id === campaign.agent_id)?.name || campaign.agent_id}
                                        </div>
                                    </div>
                                    <span className={`badge ${STATUS_BADGE[campaign.status] || "badge-danger"}`}>
                                        {campaign.status}
                                    </span>
                                </div>

                                {/* Progress bar */}
                                <div className="mb-4">
                                    <div className="flex justify-between mb-1.5">
                                        <span className="text-xs text-[var(--text-muted)]">Progress</span>
                                        <span className="text-xs font-semibold text-[var(--text-primary)]">
                                            {campaign.called} / {campaign.total_contacts} ({pct}%)
                                        </span>
                                    </div>
                                    <div className="h-1.5 bg-gray-700/50 rounded-full overflow-hidden">
                                        <div
                                            className="h-full rounded-full bg-gradient-to-r from-blue-500 to-purple-500"
                                            style={{ width: `${pct}%` }}
                                        />
                                    </div>
                                </div>

                                {/* Stats */}
                                <div className="flex gap-5 mb-5">
                                    <div>
                                        <div className="text-xl font-bold text-[var(--text-primary)]">{campaign.booked}</div>
                                        <div className="text-xs text-[var(--text-muted)]">Booked</div>
                                    </div>
                                    <div>
                                        <div className="text-xl font-bold text-[var(--text-primary)]">{convRate}%</div>
                                        <div className="text-xs text-[var(--text-muted)]">Conversion</div>
                                    </div>
                                    <div>
                                        <div className="text-xl font-bold text-[var(--text-primary)]">{campaign.failed}</div>
                                        <div className="text-xs text-[var(--text-muted)]">Failed</div>
                                    </div>
                                </div>

                                {/* Action Buttons */}
                                <div className="flex gap-2">
                                    {campaign.status === "draft" && (
                                        <button className="btn-primary flex-1 py-2 flex items-center justify-center gap-2" onClick={(e) => handleStart(campaign.id, e)}>
                                            <Play className="w-3.5 h-3.5" /> Start Campaign
                                        </button>
                                    )}
                                    {campaign.status === "active" && (
                                        <button className="flex-1 py-2 rounded-lg bg-amber-500 text-white font-semibold text-sm hover:bg-amber-400 transition-colors flex items-center justify-center gap-2 border-none cursor-pointer" onClick={(e) => handlePause(campaign.id, e)}>
                                            <Pause className="w-3.5 h-3.5" /> Pause
                                        </button>
                                    )}
                                    {campaign.status === "paused" && (
                                        <button className="btn-primary flex-1 py-2 flex items-center justify-center gap-2" onClick={(e) => handleResume(campaign.id, e)}>
                                            <Play className="w-3.5 h-3.5" /> Resume
                                        </button>
                                    )}
                                    {campaign.status === "completed" && (
                                        <button
                                            className="btn-secondary flex-1 py-2 flex items-center justify-center gap-2"
                                            onClick={(e) => handleReset(campaign.id, e)}
                                            title="Reset campaign to draft and re-run all contacts"
                                        >
                                            <RotateCcw className="w-3.5 h-3.5" /> Reset & Re-run
                                        </button>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}

            {/* New Campaign Modal */}
            <Modal
                isOpen={showNewCampaign}
                onClose={() => setShowNewCampaign(false)}
                title="New Campaign"
                width="w-[500px]"
            >
                <div className="flex flex-col gap-4">
                    <div>
                        <label className="text-[13px] text-[var(--text-muted)] mb-1.5 block">Campaign Name</label>
                        <input
                            className="input"
                            placeholder="e.g. Q1 Renewal Outreach"
                            value={newCampaignName}
                            onChange={(e) => setNewCampaignName(e.target.value)}
                        />
                    </div>

                    <div>
                        <label className="text-[13px] text-[var(--text-muted)] mb-1.5 block">Select Agent</label>
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
                        <label className="text-[13px] text-[var(--text-muted)] mb-1.5 block">Upload Contacts (CSV)</label>
                        <div
                            className={`p-8 border-2 border-dashed border-[var(--border)] rounded-xl text-center cursor-pointer text-sm transition-colors ${contactFile ? "text-[var(--text-primary)] bg-blue-500/10" : "text-[var(--text-muted)]"}`}
                            onClick={() => fileInputRef.current?.click()}
                        >
                            <div className="flex items-center justify-center gap-2">
                                {contactFile ? <FileText className="w-4 h-4" /> : <Upload className="w-4 h-4" />}
                                {contactFile ? contactFile.name : "Drop CSV or click to upload"}
                            </div>
                            <div className="text-[11px] mt-1 opacity-70">Column &apos;phone&apos; required</div>
                        </div>
                        <input
                            type="file"
                            ref={fileInputRef}
                            accept=".csv"
                            className="hidden"
                            onChange={(e) => {
                                if (e.target.files?.[0]) setContactFile(e.target.files[0]);
                            }}
                        />
                    </div>

                    <div className="flex gap-3 justify-end mt-2">
                        <button className="btn-danger" onClick={() => setShowNewCampaign(false)} disabled={isCreating}>Cancel</button>
                        <button className="btn-primary" onClick={handleCreate} disabled={isCreating}>
                            {isCreating ? "Creating..." : "Create Campaign"}
                        </button>
                    </div>
                </div>
            </Modal>
        </div>
    );
}

