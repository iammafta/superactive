import { useMemo } from 'react';
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Cell
} from 'recharts';

interface HangUpHeatmapProps {
    data: Record<string, number>;
}

export default function HangUpHeatmap({ data }: HangUpHeatmapProps) {
    const chartData = useMemo(() => {
        if (!data) return [];
        return Object.entries(data)
            .map(([state, count]) => ({ state, count }))
            .sort((a, b) => b.count - a.count); // desc
    }, [data]);

    if (chartData.length === 0) {
        return (
            <div className="h-full flex flex-col items-center justify-center text-sm text-[var(--text-muted)] p-6">
                No hang-ups recorded.
            </div>
        );
    }

    return (
        <div className="h-full w-full min-h-[250px]">
            <ResponsiveContainer width="100%" height="100%">
                <BarChart
                    data={chartData}
                    layout="vertical"
                    margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                >
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" horizontal={true} vertical={false} />
                    <XAxis
                        type="number"
                        stroke="rgba(255,255,255,0.2)"
                        tick={{ fill: 'rgba(255,255,255,0.5)', fontSize: 12 }}
                        axisLine={false}
                        tickLine={false}
                        allowDecimals={false}
                    />
                    <YAxis
                        dataKey="state"
                        type="category"
                        stroke="rgba(255,255,255,0.2)"
                        tick={{ fill: 'rgba(255,255,255,0.8)', fontSize: 12 }}
                        axisLine={false}
                        tickLine={false}
                        width={100}
                    />
                    <Tooltip
                        cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                        contentStyle={{
                            backgroundColor: 'rgba(17, 24, 39, 0.9)',
                            borderColor: 'rgba(255,255,255,0.1)',
                            borderRadius: '8px',
                            color: '#fff',
                        }}
                        itemStyle={{ color: '#ef4444' }}
                        formatter={(val: any) => [val, 'Calls']}
                    />
                    <Bar dataKey="count" radius={[0, 4, 4, 0]} barSize={20}>
                        {chartData.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={`rgba(239, 68, 68, ${Math.max(0.4, 1 - index * 0.15)})`} />
                        ))}
                    </Bar>
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
}
