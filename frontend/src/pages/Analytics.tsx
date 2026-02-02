import { useQuery } from '@tanstack/react-query'
import { analyticsApi } from '../lib/api'
import { TrendingUp, Users, Mail, MessageSquare } from 'lucide-react'
import './Analytics.css'

interface FunnelStage {
    stage: string
    count: number
    percentage?: number
}

interface FunnelResponse {
    stages: FunnelStage[]
    total_leads: number
    conversion_new_to_contacted?: number
    conversion_contacted_to_replied?: number
    conversion_replied_to_converted?: number
}

const STAGE_LABELS: Record<string, string> = {
    new: 'New',
    researching: 'Researching',
    qualified: 'Qualified',
    sequencing: 'In Sequence',
    contacted: 'Contacted',
    replied: 'Replied',
    converted: 'Converted',
}

const STAGE_COLORS = [
    '#6366f1',
    '#8b5cf6',
    '#a855f7',
    '#d946ef',
    '#ec4899',
    '#f43f5e',
    '#22c55e',
]

export default function Analytics() {
    const { data: funnel, isLoading } = useQuery<FunnelResponse>({
        queryKey: ['funnel'],
        queryFn: analyticsApi.funnel,
    })

    const formatRate = (rate?: number) => {
        if (!rate) return '—'
        return `${(Number(rate) * 100).toFixed(1)}%`
    }

    const maxCount = Math.max(...(funnel?.stages.map((s) => s.count) || [1]))

    return (
        <div className="analytics-page animate-fadeIn">
            <div className="page-header">
                <div>
                    <h1>Analytics</h1>
                    <p className="text-secondary">Track your pipeline performance</p>
                </div>
            </div>

            {isLoading ? (
                <div className="loading-state">
                    <div className="spinner" />
                </div>
            ) : (
                <>
                    {/* Conversion Cards */}
                    <div className="conversion-cards">
                        <div className="conversion-card card">
                            <div className="conversion-icon">
                                <Users size={24} />
                            </div>
                            <div className="conversion-content">
                                <span className="conversion-label">New → Contacted</span>
                                <span className="conversion-value">
                                    {formatRate(funnel?.conversion_new_to_contacted)}
                                </span>
                            </div>
                        </div>

                        <div className="conversion-card card">
                            <div className="conversion-icon">
                                <Mail size={24} />
                            </div>
                            <div className="conversion-content">
                                <span className="conversion-label">Contacted → Replied</span>
                                <span className="conversion-value">
                                    {formatRate(funnel?.conversion_contacted_to_replied)}
                                </span>
                            </div>
                        </div>

                        <div className="conversion-card card">
                            <div className="conversion-icon">
                                <TrendingUp size={24} />
                            </div>
                            <div className="conversion-content">
                                <span className="conversion-label">Replied → Converted</span>
                                <span className="conversion-value">
                                    {formatRate(funnel?.conversion_replied_to_converted)}
                                </span>
                            </div>
                        </div>
                    </div>

                    {/* Funnel Chart */}
                    <div className="funnel-section card">
                        <h2>Lead Funnel</h2>
                        <p className="text-secondary">Total: {funnel?.total_leads || 0} leads</p>

                        <div className="funnel-chart">
                            {funnel?.stages.map((stage, index) => (
                                <div key={stage.stage} className="funnel-bar-container">
                                    <div className="funnel-label">
                                        <span className="stage-name">{STAGE_LABELS[stage.stage] || stage.stage}</span>
                                        <span className="stage-count">{stage.count}</span>
                                    </div>
                                    <div className="funnel-bar-bg">
                                        <div
                                            className="funnel-bar"
                                            style={{
                                                width: `${(stage.count / maxCount) * 100}%`,
                                                backgroundColor: STAGE_COLORS[index],
                                            }}
                                        />
                                    </div>
                                    <span className="funnel-percent">
                                        {stage.percentage ? `${(Number(stage.percentage) * 100).toFixed(0)}%` : '—'}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>
                </>
            )}
        </div>
    )
}
