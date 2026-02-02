import { useQuery } from '@tanstack/react-query'
import { templatesApi } from '../lib/api'
import { FileText, Plus, BarChart2 } from 'lucide-react'
import './Templates.css'

interface Template {
    id: string
    name: string
    type: string
    touch_number: number
    subject_template: string
    body_template: string
    times_used: number
    avg_open_rate?: number
    avg_reply_rate?: number
    is_active: boolean
}

const TYPE_LABELS: Record<string, string> = {
    'trigger-led': 'Trigger-Led',
    'problem-hypothesis': 'Problem Hypothesis',
    'case-study': 'Case Study',
    'quick-question': 'Quick Question',
    'value-insight': 'Value Insight',
    'follow_up': 'Follow-Up',
    'breakup': 'Breakup',
}

export default function Templates() {
    const { data: templates = [], isLoading } = useQuery<Template[]>({
        queryKey: ['templates'],
        queryFn: () => templatesApi.list({ active_only: false }),
    })

    const formatRate = (rate?: number) => {
        if (!rate) return '—'
        return `${(rate * 100).toFixed(1)}%`
    }

    return (
        <div className="templates-page animate-fadeIn">
            <div className="page-header">
                <div>
                    <h1>Templates</h1>
                    <p className="text-secondary">Manage your email templates</p>
                </div>
                <button className="btn btn-primary">
                    <Plus size={18} />
                    New Template
                </button>
            </div>

            {isLoading ? (
                <div className="loading-state">
                    <div className="spinner" />
                </div>
            ) : templates.length === 0 ? (
                <div className="empty-state card">
                    <FileText size={48} />
                    <h3>No templates yet</h3>
                    <p>Templates help ensure consistent, high-quality emails</p>
                </div>
            ) : (
                <div className="templates-grid">
                    {templates.map((template) => (
                        <div key={template.id} className={`template-card card ${!template.is_active ? 'template-inactive' : ''}`}>
                            <div className="template-header">
                                <div className="template-type">
                                    <span className="type-badge">{TYPE_LABELS[template.type] || template.type}</span>
                                    <span className="touch-badge">T{template.touch_number}</span>
                                </div>
                                {!template.is_active && (
                                    <span className="badge badge-neutral">Inactive</span>
                                )}
                            </div>

                            <h3 className="template-name">{template.name}</h3>

                            <div className="template-preview">
                                <div className="preview-subject">
                                    <strong>Subject:</strong> {template.subject_template}
                                </div>
                            </div>

                            <div className="template-stats">
                                <div className="stat">
                                    <BarChart2 size={14} />
                                    <span>Used {template.times_used}x</span>
                                </div>
                                <div className="stat-rates">
                                    <span>Open: {formatRate(template.avg_open_rate)}</span>
                                    <span>Reply: {formatRate(template.avg_reply_rate)}</span>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}
