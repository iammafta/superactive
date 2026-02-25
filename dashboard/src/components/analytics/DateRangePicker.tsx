import { Calendar } from 'lucide-react';

interface DateRangePickerProps {
    days: number;
    onChange: (days: number) => void;
}

export default function DateRangePicker({ days, onChange }: DateRangePickerProps) {
    return (
        <div className="relative inline-flex items-center">
            <Calendar className="absolute left-3 w-4 h-4 text-gray-400 pointer-events-none" />
            <select
                value={days}
                onChange={(e) => onChange(Number(e.target.value))}
                className="pl-9 pr-8 py-2 bg-black/20 border border-white/10 rounded-lg text-sm text-white appearance-none focus:outline-none focus:border-blue-500 cursor-pointer hover:bg-black/30 transition-colors"
            >
                <option value={7}>Last 7 days</option>
                <option value={14}>Last 14 days</option>
                <option value={30}>Last 30 days</option>
                <option value={60}>Last 60 days</option>
                <option value={90}>Last 90 days</option>
            </select>
            <div className="absolute right-3 pointer-events-none text-gray-400 text-[10px]">▼</div>
        </div>
    );
}
