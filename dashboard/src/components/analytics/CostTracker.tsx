import { DollarSign } from 'lucide-react';

interface CostTrackerProps {
    totalCost: number;
    avgCostPerCall: number;
}

export default function CostTracker({ totalCost, avgCostPerCall }: CostTrackerProps) {
    return (
        <>
            <div className="glass-card hover:bg-white/[0.02] transition-colors flex flex-col justify-between" style={{ padding: 20, minHeight: 120 }}>
                <div className="flex justify-between items-start mb-2">
                    <span className="text-sm text-[var(--text-muted)] font-medium">Total Cost</span>
                    <span className="p-2 rounded-lg bg-red-500/10 text-red-400">
                        <DollarSign className="w-4 h-4" />
                    </span>
                </div>
                <div>
                    <div className="text-2xl font-bold text-[var(--text-primary)]">
                        ${(totalCost || 0).toFixed(2)}
                    </div>
                </div>
            </div>

            <div className="glass-card hover:bg-white/[0.02] transition-colors flex flex-col justify-between" style={{ padding: 20, minHeight: 120 }}>
                <div className="flex justify-between items-start mb-2">
                    <span className="text-sm text-[var(--text-muted)] font-medium">Avg Cost / Call</span>
                    <span className="p-2 rounded-lg bg-amber-500/10 text-amber-400">
                        <DollarSign className="w-4 h-4" />
                    </span>
                </div>
                <div>
                    <div className="text-2xl font-bold text-[var(--text-primary)]">
                        ${(avgCostPerCall || 0).toFixed(3)}
                    </div>
                </div>
            </div>
        </>
    );
}
