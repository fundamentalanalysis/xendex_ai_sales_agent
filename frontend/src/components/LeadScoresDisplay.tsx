import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { RefreshCw, CheckCircle, AlertTriangle } from 'lucide-react';

interface ScoreBreakdown {
    percentage: number;
    components: Record<string, number>;
    notes: string[];
}

interface LeadScoreData {
    lead_id: string;
    company_name: string;
    contact_name: string;
    fit_score: number;
    readiness_score: number;
    intent_score: number;
    composite_score: number;
    status: string;
    fit_breakdown: ScoreBreakdown;
    readiness_breakdown: ScoreBreakdown;
    intent_breakdown: ScoreBreakdown;
    validations: Record<string, boolean>;
    validation_passed: boolean;
    researched_at?: string;
}

interface Props {
    leadId: string;
    onScoresUpdated?: (scores: LeadScoreData) => void;
}

const API_BASE_URL = 'http://localhost:8000/api/v1';

export default function LeadScoresDisplay({ leadId, onScoresUpdated }: Props) {
    const [data, setData] = useState<LeadScoreData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isRecalculating, setIsRecalculating] = useState(false);

    const fetchStoredScores = async () => {
        setLoading(true);
        setError(null);
        try {
            // Fetch PREVIOUSLY calculated scores from DB
            const response = await axios.get(`${API_BASE_URL}/scoring/${leadId}/stored`);
            setData(response.data);
            if (onScoresUpdated) {
                onScoresUpdated(response.data);
            }
        } catch (err: any) {
            console.error('Error fetching stored scores:', err);
            setError('No scores available. Please run Research first.');
        } finally {
            setLoading(false);
        }
    };

    const handleForceRecalculate = async () => {
        setIsRecalculating(true);
        try {
            const response = await axios.get(`${API_BASE_URL}/scoring/${leadId}/recalculate`);
            setData(response.data);
            if (onScoresUpdated) {
                onScoresUpdated(response.data);
            }
        } catch (err: any) {
            setError('Failed to recalculate scores.');
        } finally {
            setIsRecalculating(false);
        }
    };

    useEffect(() => {
        if (leadId) {
            fetchStoredScores();
        }
    }, [leadId]);

    if (loading) {
        return (
            <div className="flex animate-pulse space-x-4 p-6 bg-slate-900 rounded-lg">
                <div className="flex-1 space-y-4 py-1">
                    <div className="h-4 bg-slate-700 rounded w-3/4"></div>
                    <div className="space-y-3">
                        <div className="h-4 bg-slate-700 rounded"></div>
                        <div className="h-4 bg-slate-700 rounded w-5/6"></div>
                    </div>
                </div>
            </div>
        );
    }

    if (error) {
        return null;
    }

    if (!data) return null;

    return (
        <div className="bg-slate-800 rounded-xl p-6 shadow-xl text-slate-200 border border-slate-700">
            <div className="flex justify-between items-center mb-6 border-b border-slate-700 pb-4">
                <div>
                    <h2 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">
                        Lead Score Intelligence
                    </h2>
                    <div className="flex items-center gap-2 mt-1">
                        <p className="text-sm text-slate-400">Factors for {data.company_name}</p>
                        {data.researched_at && (
                            <span className="text-[10px] bg-slate-700 px-1.5 py-0.5 rounded text-slate-500 font-mono">
                                Last Calculated: {new Date(data.researched_at).toLocaleDateString()}
                            </span>
                        )}
                    </div>
                </div>
                <button
                    onClick={handleForceRecalculate}
                    disabled={isRecalculating}
                    className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-slate-300 rounded-lg transition-colors text-sm font-medium border border-slate-600"
                >
                    <RefreshCw size={16} className={isRecalculating ? "animate-spin" : ""} />
                    {isRecalculating ? 'Recalculating...' : 'Refresh Formula'}
                </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
                {[
                    { label: 'Fit', value: data.fit_score * 100, color: 'text-emerald-400', border: 'border-emerald-500/30' },
                    { label: 'Readiness', value: data.readiness_score * 100, color: 'text-amber-400', border: 'border-amber-500/30' },
                ].map(score => (
                    <div key={score.label} className={`p-4 rounded-lg bg-slate-900/50 border ${score.border} flex flex-col`}>
                        <span className="text-slate-400 text-xs uppercase tracking-wider font-semibold">{score.label} Score</span>
                        <span className={`text-3xl mt-1 ${score.color}`}>{score.value.toFixed(1)}%</span>
                    </div>
                ))}
            </div>

            <div className="flex items-center justify-between gap-6 mb-6 p-4 bg-slate-900 rounded-lg">
                <div className="flex items-center gap-3">
                    <span className="font-mono text-sm text-slate-400 leading-relaxed">
                        Qualification Status:
                    </span>
                    {data.status === 'qualified' ? (
                        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded bg-emerald-500/20 text-emerald-400 text-xs font-bold border border-emerald-500/30 w-max">
                            <CheckCircle size={14} /> QUALIFIED (Both ≥40%)
                        </span>
                    ) : (
                        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded bg-slate-700 text-slate-300 text-xs font-bold w-max border border-slate-600">
                            <AlertTriangle size={14} /> UNQUALIFIED (&lt;40% in Fit or Readiness)
                        </span>
                    )}
                </div>
            </div>

            {/* Render Breakdowns */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {[
                    { title: "Fit Configuration", bd: data.fit_breakdown, color: 'emerald' },
                    { title: "Readiness Signals", bd: data.readiness_breakdown, color: 'amber' },
                ].map((block, idx) => (
                    <div key={idx} className="bg-slate-900 rounded-lg border border-slate-700/50 flex flex-col p-5 overflow-hidden col-span-1 lg:col-span-1">
                        <div className="flex justify-between items-center mb-4 border-b border-slate-800 pb-3">
                            <h3 className={`font-semibold text-${block.color}-400`}>{block.title}</h3>
                            <span className="bg-slate-800 px-2 py-0.5 rounded text-xs text-slate-300">{block.bd.percentage}%</span>
                        </div>
                        <div className="space-y-3 mb-4 flex-1">
                            {Object.entries(block.bd.components || {}).map(([key, val]) => (
                                <div key={key} className="flex justify-between items-center text-sm">
                                    <span className="text-slate-400 max-w-[70%] truncate pr-2" title={key}>{key}</span>
                                    <span className="text-slate-200 font-mono text-xs">+{val}%</span>
                                </div>
                            ))}
                        </div>

                        {block.bd.notes && block.bd.notes.length > 0 && (
                            <div className="mt-4 pt-4 border-t border-slate-800">
                                {block.bd.notes.map((note, nIdx) => (
                                    <div key={nIdx} className="text-xs text-slate-500 mb-1 leading-snug break-words">
                                        • {note}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                ))}
            </div>

        </div>
    );
}
