import React from "react";

interface PageHeaderProps {
    title: string;
    description?: string;
    action?: React.ReactNode;
}

export default function PageHeader({ title, description, action }: PageHeaderProps) {
    return (
        <div className="flex justify-between items-center mb-7">
            <div>
                <h1 className="text-2xl font-bold mb-1 text-white">{title}</h1>
                {description && (
                    <p className="text-sm text-[var(--text-muted)]">
                        {description}
                    </p>
                )}
            </div>
            {action && <div>{action}</div>}
        </div>
    );
}
