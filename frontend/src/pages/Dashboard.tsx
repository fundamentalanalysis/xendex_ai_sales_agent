
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { analyticsApi, OverviewMetrics } from '../lib/api'
import {
    Users,
    Target,
    Mail,
    MessageSquare,
    TrendingUp,
    Clock,
    CheckCircle,
    AlertCircle,
} from 'lucide-react'
import './Dashboard.css'

export default function Dashboard() {
    const { data: metrics, isLoading, error } = useQuery<OverviewMetrics>({
        queryKey: ['overview-metrics'],
        queryFn: analyticsApi.overview,
    })

    if (isLoading) {
        return (
            <div className="dashboard">
                <div className="page-header">
                    <h1>Dashboard</h1>
                </div>
                <div className="loading-state">
                    <div className="spinner" />
                    <p>Loading metrics...</p>
                </div>
            </div>
        )
    }

    if (error) {
        return (
            <div className="dashboard">
                <div className="page-header">
                    <h1>Dashboard</h1>
                </div>
                <div className="error-state">
                    <AlertCircle />
                    <p>Failed to load metrics. Is the backend running?</p>
                </div>
            </div>
        )
    }

    const stats = [
        {
            label: 'Total Leads',
            value: metrics?.total_leads || 0,
            icon: Users,
            color: 'blue',
            link: '/leads',
        },
        {
            label: 'Qualified',
            value: metrics?.leads_qualified || 0,
            icon: Target,
            color: 'green',
            link: '/leads?status=qualified',
        },
        {
            label: 'In Sequence',
            value: metrics?.leads_in_sequence || 0,
            icon: Clock,
            color: 'purple',
            link: '/in-sequence',
        },
        {
            label: 'Contacted',
            value: metrics?.leads_contacted || 0,
            icon: Mail,
            color: 'indigo',
            link: '/leads?status=all_contacted',
        },
        {
            label: 'Replied',
            value: metrics?.leads_replied || 0,
            icon: MessageSquare,
            color: 'emerald',
            link: '/leads?status=replied',
        },
        {
            label: 'Active Campaigns',
            value: metrics?.active_campaigns || 0,
            icon: TrendingUp,
            color: 'orange',
            link: '/campaigns',
        },
    ]

    return (
        <div className="dashboard animate-fadeIn">
            <div className="page-header">
                <h1>Dashboard</h1>
                <p className="text-secondary">Overview of your sales pipeline</p>
            </div>

            {/* Stats Grid */}
            <div className="stats-grid">
                {stats.map((stat) => (
                    <Link key={stat.label} to={stat.link} className={`stat-card stat-${stat.color}`}>
                        <div className="stat-icon">
                            <stat.icon />
                        </div>
                        <div className="stat-content">
                            <span className="stat-value">{stat.value.toLocaleString()}</span>
                            <span className="stat-label">{stat.label}</span>
                        </div>
                    </Link>
                ))}
            </div>

            {/* Quick Actions */}
            <div className="dashboard-section">
                <h2>Quick Actions</h2>
                <div className="quick-actions">
                    <Link to="/drafts?status=pending" className="action-card">
                        <div className="action-icon pending">
                            <Clock />
                        </div>
                        <div className="action-content">
                            <span className="action-value">{metrics?.pending_approvals || 0}</span>
                            <span className="action-label">Pending Approvals</span>
                        </div>
                    </Link>

                    <Link to="/leads" className="action-card">
                        <div className="action-icon success">
                            <CheckCircle />
                        </div>
                        <div className="action-content">
                            <span className="action-value">{metrics?.leads_researched || 0}</span>
                            <span className="action-label">Researched Leads</span>
                        </div>
                    </Link>
                </div>
            </div>

            {/* Email Performance */}
            <div className="dashboard-section">
                <h2>7-Day Email Performance</h2>
                <div className="performance-cards">
                    <div className="perf-card">
                        <span className="perf-label">Emails Sent</span>
                        <span className="perf-value">{metrics?.emails_sent_7d || 0}</span>
                    </div>
                    <div className="perf-card">
                        <span className="perf-label">Open Rate</span>
                        <span className="perf-value">
                            {metrics?.open_rate_7d
                                ? `${(Number(metrics.open_rate_7d) * 100).toFixed(1)}%`
                                : '—'}
                        </span>
                    </div>
                    <div className="perf-card">
                        <span className="perf-label">Reply Rate</span>
                        <span className="perf-value">
                            {metrics?.reply_rate_7d
                                ? `${(Number(metrics.reply_rate_7d) * 100).toFixed(1)}%`
                                : '—'}
                        </span>
                    </div>
                </div>
            </div>
        </div>
    )
}
