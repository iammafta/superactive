import React from "react";

interface EmptyStateProps {
    icon: React.ElementType;
    title: string;
    description: string;
    action?: React.ReactNode;
}

export default function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
    return (
        <div className="flex flex-col items-center justify-center p-12 text-center h-full min-h-[300px] border-2 border-dashed border-white/5 rounded-2xl bg-white/[0.01]">
            <div className="w-16 h-16 rounded-2xl bg-white/5 flex items-center justify-center mb-5 border border-white/10">
                <Icon className="w-8 h-8 text-[var(--text-muted)]" strokeWidth={1.5} />
            </div>
            <h3 className="text-lg font-bold text-white mb-2">{title}</h3>
            <p className="text-sm text-[var(--text-muted)] max-w-[400px] leading-relaxed mb-6">
                {description}
            </p>
            {action && <div>{action}</div>}
        </div>
    );
}
