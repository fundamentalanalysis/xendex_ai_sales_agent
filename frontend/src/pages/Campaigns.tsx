import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { inSequenceApi, Campaign } from '../lib/api'
import { Plus, Play, Pause, Users, Mail, TrendingUp, Trash2 } from 'lucide-react'
import './Campaigns.css'

const STATUS_COLORS: Record<string, string> = {
    draft: 'neutral',
    active: 'success',
    paused: 'warning',
    completed: 'info',
}

export default function Campaigns() {
    const queryClient = useQueryClient()
    const [showCreate, setShowCreate] = useState(false)

    const { data, isLoading } = useQuery({
        queryKey: ['campaigns'],
        queryFn: () => inSequenceApi.list(),
    })

    const startMutation = useMutation({
        mutationFn: inSequenceApi.start,
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['campaigns'] }),
    })

    const pauseMutation = useMutation({
        mutationFn: inSequenceApi.pause,
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['campaigns'] }),
    })

    const deleteMutation = useMutation({
        mutationFn: inSequenceApi.delete,
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['campaigns'] }),
    })

    const campaigns: Campaign[] = data?.items || []

    return (
        <div className="campaigns-page animate-fadeIn">
            <div className="page-header">
                <div>
                    <h1>Campaigns</h1>
                    <p className="text-secondary">Manage your outreach sequences</p>
                </div>
                <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
                    <Plus size={18} />
                    New Campaign
                </button>
            </div>

            {isLoading ? (
                <div className="loading-state">
                    <div className="spinner" />
                </div>
            ) : campaigns.length === 0 ? (
                <div className="empty-state card">
                    <TrendingUp size={48} />
                    <h3>No campaigns yet</h3>
                    <p>Create your first campaign to start reaching out to leads</p>
                    <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
                        <Plus size={18} />
                        Create Campaign
                    </button>
                </div>
            ) : (
                <div className="campaigns-grid">
                    {campaigns.map((campaign) => (
                        <div key={campaign.id} className="campaign-card card">
                            <div className="campaign-header">
                                <h3>{campaign.name}</h3>
                                <span className={`badge badge-${STATUS_COLORS[campaign.status]}`}>
                                    {campaign.status}
                                </span>
                            </div>

                            {campaign.description && (
                                <p className="campaign-description">{campaign.description}</p>
                            )}

                            <div className="campaign-stats">
                                <div className="stat">
                                    <Users size={16} />
                                    <span>{campaign.total_leads || 0} leads</span>
                                </div>
                                <div className="stat">
                                    <Mail size={16} />
                                    <span>{campaign.sequence_touches} touches</span>
                                </div>
                            </div>

                            <div className="campaign-meta">
                                {campaign.target_industry && (
                                    <span className="meta-tag">{campaign.target_industry}</span>
                                )}
                                {campaign.target_persona && (
                                    <span className="meta-tag">{campaign.target_persona}</span>
                                )}
                            </div>

                            <div className="campaign-actions">
                                {campaign.status === 'active' ? (
                                    <button
                                        className="btn btn-secondary btn-sm"
                                        onClick={() => pauseMutation.mutate(campaign.id)}
                                    >
                                        <Pause size={16} />
                                        Pause
                                    </button>
                                ) : (
                                    <button
                                        className="btn btn-primary btn-sm"
                                        onClick={() => startMutation.mutate(campaign.id)}
                                    >
                                        <Play size={16} />
                                        Start
                                    </button>
                                )}
                                {campaign.status !== 'active' && (
                                    <button
                                        className="btn btn-icon btn-sm"
                                        title="Delete Campaign"
                                        onClick={() => {
                                            if (confirm('Are you sure you want to delete this campaign?')) {
                                                deleteMutation.mutate(campaign.id)
                                            }
                                        }}
                                    >
                                        <Trash2 size={16} className="text-error" />
                                    </button>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}
