
import { useState, useRef, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { leadsApi, Lead, draftsApi, BulkImportResult, debugApi, emailsApi } from '../lib/api'
import {
    Search,
    Plus,
    RefreshCw,
    ChevronLeft,
    ChevronRight,
    ExternalLink,
    Zap,
    PenTool,
    Trash2,
    Eye,
    X,
    AlertCircle,
    Building2,
    Linkedin,
    Lightbulb,
    BarChart3,
    Upload,
    FileSpreadsheet,
    Edit2,
    CheckCircle,
    Mail,
    Target
} from 'lucide-react'
import './Leads.css'


const STATUS_COLORS: Record<string, string> = {
    new: 'neutral',
    researching: 'info',
    qualified: 'success',
    sequencing: 'info',
    inprogress: 'info',
    contacted: 'warning',
    replied: 'success',
    converted: 'success',
    disqualified: 'error',
}

export default function Leads() {
    const queryClient = useQueryClient()
    const [searchParams] = useSearchParams()
    const [page, setPage] = useState(1)
    const [search, setSearch] = useState('')
    const [statusFilter, setStatusFilter] = useState(searchParams.get('status') || '')
    const [selectedLeadId, setSelectedLeadId] = useState<string | null>(null)
    const [viewingEmailsId, setViewingEmailsId] = useState<string | null>(null)
    const [editingLead, setEditingLead] = useState<Lead | null>(null)

    const { data, isLoading } = useQuery({
        queryKey: ['leads', page, search, statusFilter],
        queryFn: () => leadsApi.list({ page, search: search || undefined, status: statusFilter || undefined }),
    })

    const leads: Lead[] = data?.items || []
    const totalPages = data?.pages || 1

    const [showCreateModal, setShowCreateModal] = useState(false)
    const [showImportModal, setShowImportModal] = useState(false)
    const [newLead, setNewLead] = useState<Partial<Lead>>({
        company_name: '',
        company_domain: '',
        email: '',
        first_name: '',
        last_name: '',
        linkedin_url: '',
        industry: '',
        mobile: '',
        num_followups: 3,
        followup_delay_days: 3,
    })

    const createMutation = useMutation({
        mutationFn: leadsApi.create,
        onSuccess: () => {
            debugApi.terminalLog(`New lead created successfully.`)
            queryClient.invalidateQueries({ queryKey: ['leads'] })
            setShowCreateModal(false)
            setNewLead({
                company_name: '',
                company_domain: '',
                email: '',
                first_name: '',
                last_name: '',
                linkedin_url: '',
                industry: '',
                mobile: '',
                num_followups: 3,
                followup_delay_days: 3,
            })
        },
    })

    const handleCreateSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        createMutation.mutate(newLead)
    }

    return (
        <div className="leads-page animate-fadeIn">
            <div className="page-header">
                <div>
                    <h1>{statusFilter === 'replied' ? 'Replied Leads' : 'Leads'}</h1>
                    <p className="text-secondary">Manage and research your leads</p>
                </div>
                <div className="header-actions">
                    <button
                        className="btn btn-secondary"
                        onClick={() => setShowImportModal(true)}
                    >
                        <Upload size={18} />
                        Import Leads
                    </button>
                    <button
                        className="btn btn-primary"
                        onClick={() => setShowCreateModal(true)}
                    >
                        <Plus size={18} />
                        Add Lead
                    </button>
                </div>
            </div>

            {/* Filters */}
            <div className="filters-bar">
                <div className="search-input">
                    <Search size={18} />
                    <input
                        type="text"
                        className="input"
                        placeholder="Search leads..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                    />
                </div>

                <select
                    className="input filter-select"
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                >
                    <option value="">All Statuses</option>
                    <option value="new">New</option>
                    <option value="researching">Researching</option>
                    <option value="qualified">Qualified</option>
                    <option value="sequencing">In Sequence</option>
                    <option value="sequencing">In Sequence</option>
                    <option value="contacted">Contacted (Exact)</option>
                    <option value="all_contacted">All Contacted</option>
                    <option value="replied">Replied</option>
                </select>
            </div>

            {/* Leads Table */}
            <div className="card">
                {isLoading ? (
                    <div className="loading-state">
                        <div className="spinner" />
                    </div>
                ) : leads.length === 0 ? (
                    <div className="empty-state">
                        <p>No leads found</p>
                    </div>
                ) : (
                    <table className="table leads-table">
                        <thead>
                            <tr>
                                <th>Company</th>
                                <th>Contact</th>
                                <th>Status</th>
                                <th>Fit</th>
                                <th>Readiness</th>
                                <th>Intent</th>
                                <th>Composite</th>
                                <th>Industry</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {leads.map((lead) => (
                                <LeadRow
                                    key={lead.id}
                                    lead={lead}
                                    onViewResearch={(id) => setSelectedLeadId(id)}
                                    onViewEmails={(id) => setViewingEmailsId(id)}
                                    onEdit={(l) => setEditingLead(l)}
                                />
                            ))}
                        </tbody>
                    </table>
                )}

                {/* Pagination */}
                {totalPages > 1 && (
                    <div className="pagination">
                        <button
                            className="btn btn-ghost btn-sm"
                            onClick={() => setPage((p) => Math.max(1, p - 1))}
                            disabled={page === 1}
                        >
                            <ChevronLeft size={18} />
                            Previous
                        </button>
                        <span className="page-info">
                            Page {page} of {totalPages}
                        </span>
                        <button
                            className="btn btn-ghost btn-sm"
                            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                            disabled={page === totalPages}
                        >
                            Next
                            <ChevronRight size={18} />
                        </button>
                    </div>
                )}
            </div>

            {showCreateModal && (
                <div className="modal-overlay">
                    <div className="modal card modal-v2">
                        <div className="modal-header">
                            <h2>Add New Lead</h2>
                            <button
                                className="close-btn"
                                onClick={() => setShowCreateModal(false)}
                            >
                                <X size={18} />
                                <span>Close</span>
                            </button>
                        </div>
                        <form onSubmit={handleCreateSubmit} className="modal-form">
                            <div className="form-group">
                                <label>Company Name *</label>
                                <input
                                    required
                                    className="input"
                                    value={newLead.company_name}
                                    onChange={e => setNewLead({ ...newLead, company_name: e.target.value })}
                                />
                            </div>
                            <div className="form-group">
                                <label>Company Domain *</label>
                                <input
                                    required
                                    className="input"
                                    placeholder="example.com"
                                    value={newLead.company_domain}
                                    onChange={e => setNewLead({ ...newLead, company_domain: e.target.value })}
                                />
                            </div>
                            <div className="form-row">
                                <div className="form-group">
                                    <label>First Name</label>
                                    <input
                                        className="input"
                                        value={newLead.first_name}
                                        onChange={e => setNewLead({ ...newLead, first_name: e.target.value })}
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Last Name</label>
                                    <input
                                        className="input"
                                        value={newLead.last_name}
                                        onChange={e => setNewLead({ ...newLead, last_name: e.target.value })}
                                    />
                                </div>
                            </div>
                            <div className="form-group">
                                <label>Email *</label>
                                <input
                                    required
                                    type="email"
                                    className="input"
                                    value={newLead.email}
                                    onChange={e => setNewLead({ ...newLead, email: e.target.value })}
                                />
                            </div>
                            <div className="form-group">
                                <label>LinkedIn URL</label>
                                <input
                                    className="input"
                                    value={newLead.linkedin_url}
                                    onChange={e => setNewLead({ ...newLead, linkedin_url: e.target.value })}
                                />
                            </div>
                            <div className="form-row">
                                <div className="form-group">
                                    <label>Industry</label>
                                    <input
                                        className="input"
                                        placeholder="e.g. Healthcare, Finance"
                                        value={newLead.industry}
                                        onChange={e => setNewLead({ ...newLead, industry: e.target.value })}
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Mobile Number</label>
                                    <input
                                        className="input"
                                        placeholder="+1 555 123 4567"
                                        value={newLead.mobile}
                                        onChange={e => setNewLead({ ...newLead, mobile: e.target.value })}
                                    />
                                </div>
                            </div>

                            <div className="modal-actions-v2">
                                <button
                                    type="button"
                                    className="cancel-btn"
                                    onClick={() => setShowCreateModal(false)}
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    className="btn btn-primary"
                                    disabled={createMutation.isPending}
                                >
                                    {createMutation.isPending ? 'Creating...' : 'Create Lead'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div >
            )
            }

            {
                selectedLeadId && (
                    <ResearchPanel
                        leadId={selectedLeadId}
                        onClose={() => setSelectedLeadId(null)}
                    />
                )
            }

            {
                viewingEmailsId && (
                    <EmailsPanel
                        leadId={viewingEmailsId}
                        onClose={() => setViewingEmailsId(null)}
                    />
                )
            }

            {
                showImportModal && (
                    <BulkImportModal
                        onClose={() => setShowImportModal(false)}
                        onSuccess={() => {
                            queryClient.invalidateQueries({ queryKey: ['leads'] })
                            setShowImportModal(false)
                        }}
                    />
                )
            }

            {
                editingLead && (
                    <EditLeadModal
                        lead={editingLead}
                        onClose={() => setEditingLead(null)}
                        onSuccess={() => {
                            queryClient.invalidateQueries({ queryKey: ['leads'] })
                            setEditingLead(null)
                        }}
                    />
                )
            }
        </div >
    )
}

function LeadRow({
    lead,
    onViewResearch,
    onViewEmails,
    onEdit
}: {
    lead: Lead;
    onViewResearch: (id: string) => void;
    onViewEmails: (id: string) => void;
    onEdit: (lead: Lead) => void;
}) {
    const queryClient = useQueryClient()

    const researchMutation = useMutation({
        mutationFn: (id: string) => leadsApi.triggerResearch(id),
        onSuccess: (_, id) => {
            debugApi.terminalLog(`Research triggered for lead ${id}`)
            queryClient.invalidateQueries({ queryKey: ['leads'] })
        },
    })

    const generateDraftMutation = useMutation({
        mutationFn: (leadId: string) => draftsApi.generate({ lead_ids: [leadId] }),
        onSuccess: (_, leadId) => {
            debugApi.terminalLog(`Draft generation initiated for lead ${leadId}`)
            queryClient.invalidateQueries({ queryKey: ['leads'] })
        },
    })

    const deleteMutation = useMutation({
        mutationFn: leadsApi.delete,
        onSuccess: (_, id) => {
            debugApi.terminalLog(`Lead deleted: ${id}`)
            queryClient.invalidateQueries({ queryKey: ['leads'] })
        },
    })

    const formatScore = (score?: number) => {
        if (score === undefined || score === null) return '—'
        return `${Math.round(score * 100)}%`
    }

    return (
        <tr>
            <td>
                <div className="company-cell">
                    <span className="company-name">{lead.company_name}</span>
                    <a href={`https://${lead.company_domain}`} target="_blank" rel="noopener noreferrer" className="company-domain">
                        {lead.company_domain} <ExternalLink size={12} />
                    </a>
                </div>
            </td>
            <td>
                <div className="contact-cell">
                    <span className="contact-name">{lead.first_name} {lead.last_name}</span>
                    <span className="contact-email">{lead.email}</span>
                </div>
            </td>
            <td>
                <span className={`badge badge-${STATUS_COLORS[lead.status] || 'neutral'}`}>{lead.status}</span>
                {lead.has_replied && (
                    <span className="badge badge-success" title="Lead has replied">
                        ✓ Replied
                    </span>
                )}
            </td>
            <td><span className="score-value fit">{formatScore(lead.fit_score)}</span></td>
            <td><span className="score-value readiness">{formatScore(lead.readiness_score)}</span></td>
            <td><span className="score-value intent">{formatScore(lead.intent_score)}</span></td>
            <td>
                <div className="score-cell">
                    <span className="score-value composite">{formatScore(lead.composite_score)}</span>
                    {lead.composite_score !== undefined && (
                        <div className="score-bar">
                            <div className="score-fill" style={{ width: `${lead.composite_score * 100}%` }} />
                        </div>
                    )}
                </div>
            </td>
            <td className="text-secondary">{lead.industry || '—'}</td>
            <td>
                <div className="actions-cell">
                    <button className="btn btn-ghost btn-sm" onClick={() => researchMutation.mutate(lead.id)} disabled={researchMutation.isPending} title="Run Research">
                        {researchMutation.isPending ? <RefreshCw size={16} className="animate-spin" /> : <Zap size={16} />}
                    </button>
                    {lead.researched_at && (
                        <button className="btn btn-ghost btn-sm" onClick={() => onViewResearch(lead.id)} title="View Research">
                            <Eye size={16} />
                        </button>
                    )}
                    <button className="btn btn-ghost btn-sm" onClick={() => onViewEmails(lead.id)} title="View Emails">
                        <Mail size={16} />
                    </button>
                    {(lead.status === 'qualified' || lead.researched_at) && (
                        <button className="btn btn-ghost btn-sm" onClick={() => generateDraftMutation.mutate(lead.id)} disabled={generateDraftMutation.isPending} title="Generate Draft">
                            <PenTool size={16} />
                        </button>
                    )}
                    <button className="btn btn-ghost btn-sm" onClick={() => onEdit(lead)} title="Edit Lead">
                        <Edit2 size={16} />
                    </button>
                    <button className="btn btn-ghost btn-sm btn-danger" onClick={() => deleteMutation.mutate(lead.id)} disabled={deleteMutation.isPending} title="Delete Lead">
                        <Trash2 size={16} />
                    </button>
                </div>
            </td>
        </tr>
    )
}

function ResearchPanel({ leadId, onClose }: { leadId: string; onClose: () => void }) {
    const { data, isLoading } = useQuery({
        queryKey: ['intelligence', leadId],
        queryFn: () => leadsApi.getIntelligence(leadId),
    })

    const formatScore = (score?: number) => {
        if (score === undefined || score === null) return '—'
        return `${Math.round(score * 100)}%`
    }

    const formatDate = (dateStr?: string) => {
        if (!dateStr) return '—'
        return new Date(dateStr).toLocaleString()
    }

    const renderListItems = (items: any[]) => {
        if (!Array.isArray(items)) return <li>{String(items)}</li>
        return items.map((item, i) => {
            let content = item;
            // Check if item is a JSON string
            if (typeof item === 'string' && (item.trim().startsWith('{') || item.trim().startsWith('['))) {
                try {
                    const parsed = JSON.parse(item);
                    content = parsed;
                } catch (e) {
                    // Not valid JSON, stick with string
                }
            }

            if (typeof content === 'object' && content !== null) {
                // Handle the specific structure seen in screenshots: {evidence, indicator}
                if (content.indicator || content.evidence) {
                    return (
                        <li key={i}>
                            {content.indicator && <strong>{content.indicator}: </strong>}
                            {content.evidence}
                        </li>
                    )
                }
                const text = content.hypothesis || content.name || content.description || content.title || JSON.stringify(content);
                return <li key={i}>{text}</li>
            }
            return <li key={i}>{content}</li>
        })
    }

    if (isLoading) return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal card" onClick={(e) => e.stopPropagation()}>
                <div className="loading-state"><div className="spinner" /><p>Loading research...</p></div>
            </div>
        </div>
    )

    if (!data) return null;

    const analysis = data.lead_analysis || {};
    const linkedin = data.linkedin || {};
    const insights = data.insights || {};

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal research-panel card" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <h2><BarChart3 size={24} /> Research Report</h2>
                    <button className="btn btn-ghost btn-sm" onClick={onClose}><X size={20} /></button>
                </div>

                <div className="research-content">
                    <div className="research-header">
                        <div><h3>{data.lead?.company_name}</h3><span className="text-secondary">{data.lead?.company_domain}</span></div>
                        <div className="research-meta"><span>Researched: {formatDate(data.researched_at)}</span></div>
                    </div>

                    <div className="research-section">
                        <h4>Scores</h4>
                        <div className="scores-grid">
                            <div className="score-card"><span className="score-label">Fit</span><span>{formatScore(data.scores?.fit_score)}</span></div>
                            <div className="score-card"><span className="score-label">Readiness</span><span>{formatScore(data.scores?.readiness_score)}</span></div>
                            <div className="score-card"><span className="score-label">Intent</span><span>{formatScore(data.scores?.intent_score)}</span></div>
                            <div className="score-card highlight"><span className="score-label">Composite</span><span>{formatScore(data.scores?.composite_score)}</span></div>
                        </div>
                    </div>

                    {/* Lead Company Analysis */}
                    <div className="research-section">
                        <h4><Building2 size={16} /> Lead Company Analysis</h4>
                        <div className="analysis-grid">
                            <div className="analysis-item">
                                <span className="label" style={{ color: '#3b82f6', fontSize: '0.9rem' }}>Offerings:</span>
                                {analysis.offerings && analysis.offerings.length > 0 ? (
                                    <ul className="bullet-list">
                                        {renderListItems(analysis.offerings)}
                                    </ul>
                                ) : <p className="text-secondary text-sm italic">No offerings detected.</p>}
                            </div>

                            <div className="analysis-item">
                                <span className="label" style={{ color: '#3b82f6', fontSize: '0.9rem' }}>Pain Indicators:</span>
                                {analysis.pain_indicators && analysis.pain_indicators.length > 0 ? (
                                    <ul className="bullet-list">
                                        {renderListItems(analysis.pain_indicators)}
                                    </ul>
                                ) : <p className="text-secondary text-sm italic">No pain indicators found.</p>}
                            </div>

                            <div className="analysis-item">
                                <span className="label" style={{ color: '#3b82f6', fontSize: '0.9rem' }}>Buying Signals:</span>
                                {analysis.buying_signals && analysis.buying_signals.length > 0 ? (
                                    <ul className="bullet-list">
                                        {renderListItems(analysis.buying_signals)}
                                    </ul>
                                ) : <p className="text-secondary text-sm italic">No buying signals found.</p>}
                            </div>
                        </div>
                    </div>

                    {/* LinkedIn Intelligence */}
                    <div className="research-section">
                        <h4><Linkedin size={16} /> LinkedIn Intelligence</h4>
                        <div className="linkedin-grid">
                            <div className="info-row">
                                <span className="label">Seniority:</span>
                                <span className={`badge badge-${linkedin.seniority === 'executive' || linkedin.seniority === 'director' ? 'warning' : 'info'}`}>
                                    {linkedin.seniority ? linkedin.seniority.toLowerCase() : 'unknown'}
                                </span>
                            </div>
                            <div className="info-row">
                                <span className="label">Decision Maker:</span>
                                <span className={`badge badge-${linkedin.decision_power ? 'success' : 'neutral'}`} style={!linkedin.decision_power ? { color: '#666', background: '#e5e7eb' } : {}}>
                                    {linkedin.decision_power ? 'Yes' : '× No'}
                                </span>
                            </div>
                            <div className="info-row">
                                <span className="label">Budget Authority:</span>
                                <span className={`badge badge-${linkedin.budget_authority && linkedin.budget_authority !== 'none' ? 'success' : 'warning'}`} style={!linkedin.budget_authority || linkedin.budget_authority === 'none' ? { color: '#b45309', background: '#fef3c7' } : {}}>
                                    {linkedin.budget_authority || 'none'}
                                </span>
                            </div>
                            <div className="info-row">
                                <span className="label">LinkedIn Lead Score:</span>
                                <span className="badge badge-neutral" style={{ background: '#f3f4f6', color: '#374151' }}>
                                    {linkedin.lead_score !== undefined ? `${linkedin.lead_score}/100` : '0/100'}
                                </span>
                            </div>

                            {linkedin.cold_email_hooks && linkedin.cold_email_hooks.length > 0 && (
                                <div className="mt-3">
                                    <span style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600, color: '#ec4899', marginBottom: '8px' }}>
                                        <Target size={16} /> Cold Email Hooks:
                                    </span>
                                    <ul className="bullet-list">
                                        {renderListItems(linkedin.cold_email_hooks)}
                                    </ul>
                                </div>
                            )}

                            {linkedin.opening_line && (
                                <div className="suggestion-box mt-3">
                                    <span className="label block mb-1">Suggested Opening Line:</span>
                                    <p className="italic text-secondary">"{linkedin.opening_line}"</p>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* AI Insights */}
                    <div className="research-section">
                        <h4><Lightbulb size={16} /> AI-Generated Insights</h4>
                        <div className="insights-content">
                            <div className="insight-block">
                                <span className="label">Pain Hypotheses:</span>
                                {insights.pain_hypotheses && insights.pain_hypotheses.length > 0 ? (
                                    <ul className="bullet-list">
                                        {renderListItems(insights.pain_hypotheses)}
                                    </ul>
                                ) : <p className="text-secondary text-sm italic">No hypotheses generated.</p>}
                            </div>

                            {insights.best_angle && (
                                <div className="insight-block mt-3">
                                    <span className="label">Best Angle:</span>
                                    <p className="text-body">{insights.best_angle}</p>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}

function EmailTimelineItem({ item }: { item: any }) {
    // Only fetch details if it's a received email (since list view lacks body)
    const { data: detail, isLoading } = useQuery({
        queryKey: ['email-detail', item.raw.id],
        queryFn: () => emailsApi.getReceived(item.raw.id),
        enabled: item.type === 'received',
        staleTime: Infinity
    })

    const formatDate = (dateStr?: string) => {
        if (!dateStr) return '—'
        return new Date(dateStr).toLocaleString()
    }

    // Determine content to show
    let content = item.content; // Default for sent
    if (item.type === 'received') {
        if (isLoading) content = "<p>Loading content...</p>";
        else if (detail?.html_body || detail?.html) content = detail.html_body || detail.html;
        else if (detail?.text_body || detail?.text) content = `<pre>${detail.text_body || detail.text}</pre>`;
        else content = "<p class='text-secondary italic'>No content available.</p>";
    }

    return (
        <div className={`event-card ${item.type}`}>
            <div className="event-header">
                <span className={`badge badge-${item.type === 'sent' ? 'primary' : 'info'}`}>
                    {item.type.toUpperCase()}
                </span>
                <span className="event-date">{formatDate(item.date)}</span>
            </div>
            <div className="event-title">{item.title}</div>
            <div className="event-body">
                {item.type === 'received' && (
                    <div className="mb-2 text-xs text-secondary border-b pb-2 mb-2">
                        <p><strong>From:</strong> {item.raw.from}</p>
                        <p><strong>To:</strong> {item.raw.to.join(', ')}</p>
                    </div>
                )}
                <div
                    className="email-content prose prose-sm max-w-none"
                    dangerouslySetInnerHTML={{ __html: content || '' }}
                />
            </div>
        </div>
    )
}

function EmailsPanel({ leadId, onClose }: { leadId: string; onClose: () => void }) {
    const queryClient = useQueryClient()
    const [showReplyModal, setShowReplyModal] = useState(false)
    const [replySubject, setReplySubject] = useState('')
    const [replyBody, setReplyBody] = useState('')

    const { data: leadData, isLoading: isLoadingLead } = useQuery({
        queryKey: ['intelligence', leadId],
        queryFn: () => leadsApi.getIntelligence(leadId),
    })

    const { data: receivedEmails, isLoading: isLoadingEmails } = useQuery({
        queryKey: ['received-emails'],
        queryFn: emailsApi.listReceived,
    })

    const sendReplyMutation = useMutation({
        mutationFn: () => emailsApi.sendReply(leadId, replySubject, replyBody),
        onSuccess: () => {
            debugApi.terminalLog(`Reply sent to ${leadData?.lead?.email}`)
            queryClient.invalidateQueries({ queryKey: ['intelligence', leadId] })
            setShowReplyModal(false)
            setReplySubject('')
            setReplyBody('')
        },
        onError: (err: any) => {
            debugApi.terminalLog(`Failed to send reply: ${err.message}`, 'error')
            alert('Failed to send reply. Please try again.')
        }
    })

    if (isLoadingLead || isLoadingEmails) return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal card" onClick={(e) => e.stopPropagation()}>
                <div className="loading-state"><div className="spinner" /><p>Loading emails...</p></div>
            </div>
        </div>
    )

    if (!leadData) return null;

    // Filter emails for this lead
    const leadEmail = leadData.lead?.email?.toLowerCase();
    const relevantReceived = receivedEmails?.data.filter((email: any) =>
        (email.from && email.from.toLowerCase().includes(leadEmail)) ||
        (email.to && email.to.some((t: string) => t.toLowerCase().includes(leadEmail))) ||
        (email.from && leadEmail && email.from.toLowerCase().includes(leadEmail))
    ) || [];

    const sentEvents = leadData.events?.filter((e: any) => e.event_type === 'sent') || [];

    // Combine and Sort
    const timeline = [
        ...sentEvents.map((e: any) => ({
            type: 'sent',
            date: e.created_at,
            title: e.title || 'Email Sent',
            content: e.body,
            raw: e
        })),
        ...relevantReceived.map((e: any) => ({
            type: 'received',
            date: e.created_at,
            title: e.subject || 'No Subject',
            content: null,
            raw: e
        }))
    ].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

    // Get most recent received email for reply context
    const lastReceivedEmail = relevantReceived[0];
    const handleReplyClick = () => {
        if (lastReceivedEmail) {
            setReplySubject(`Re: ${lastReceivedEmail.subject || 'Your message'}`)
        } else {
            setReplySubject('Follow up')
        }
        setReplyBody('')
        setShowReplyModal(true)
    }

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal research-panel card" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <h2><Mail size={24} /> Email History</h2>
                    <button className="btn btn-ghost btn-sm" onClick={onClose}><X size={20} /></button>
                </div>

                <div className="research-content">
                    <div className="research-header">
                        <div><h3>{leadData.lead?.company_name}</h3><span className="text-secondary">{leadData.lead?.email}</span></div>
                        <button className="btn btn-primary btn-sm" onClick={handleReplyClick}>
                            <Mail size={16} /> Reply
                        </button>
                    </div>

                    <div className="research-section">
                        <div className="events-timeline">
                            {timeline.length === 0 ? (
                                <p className="text-secondary">No email history found with this contact.</p>
                            ) : (
                                timeline.map((item, i) => (
                                    <EmailTimelineItem key={i} item={item} />
                                ))
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {showReplyModal && (
                <div className="modal-overlay" style={{ zIndex: 1001 }} onClick={() => setShowReplyModal(false)}>
                    <div className="modal card" style={{ maxWidth: '700px' }} onClick={(e) => e.stopPropagation()}>
                        <div className="modal-header">
                            <h2><Mail size={20} /> Compose Reply</h2>
                            <button className="btn btn-ghost btn-sm" onClick={() => setShowReplyModal(false)}><X size={20} /></button>
                        </div>
                        <div className="modal-body" style={{ padding: '1.5rem' }}>
                            <div className="form-group" style={{ marginBottom: '1rem' }}>
                                <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600 }}>To:</label>
                                <input
                                    className="input"
                                    value={leadData.lead?.email || ''}
                                    disabled
                                    style={{ backgroundColor: '#f3f4f6', cursor: 'not-allowed' }}
                                />
                            </div>
                            <div className="form-group" style={{ marginBottom: '1rem' }}>
                                <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600 }}>Subject:</label>
                                <input
                                    className="input"
                                    value={replySubject}
                                    onChange={(e) => setReplySubject(e.target.value)}
                                    placeholder="Email subject..."
                                />
                            </div>
                            <div className="form-group">
                                <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600 }}>Message:</label>
                                <textarea
                                    className="input"
                                    value={replyBody}
                                    onChange={(e) => setReplyBody(e.target.value)}
                                    placeholder="Type your message here..."
                                    rows={12}
                                    style={{ fontFamily: 'inherit', resize: 'vertical' }}
                                />
                            </div>
                        </div>
                        <div className="modal-actions" style={{ padding: '1rem 1.5rem', display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
                            <button className="btn btn-ghost" onClick={() => setShowReplyModal(false)}>Cancel</button>
                            <button
                                className="btn btn-primary"
                                onClick={() => sendReplyMutation.mutate()}
                                disabled={!replySubject || !replyBody || sendReplyMutation.isPending}
                            >
                                {sendReplyMutation.isPending ? 'Sending...' : 'Send Reply'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}

function BulkImportModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
    const [isDragging, setIsDragging] = useState(false)
    const [selectedFile, setSelectedFile] = useState<File | null>(null)
    const [result, setResult] = useState<BulkImportResult | null>(null)
    const fileInputRef = useRef<HTMLInputElement>(null)

    const uploadMutation = useMutation({
        mutationFn: leadsApi.bulkImport,
        onSuccess: (data) => {
            debugApi.terminalLog(`Bulk import complete: ${data.created} created`)
            setResult(data)
        },
        onError: (err: any) => {
            debugApi.terminalLog(`Bulk import failed: ${err.message}`, 'error')
        },
    })

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault(); setIsDragging(false)
        const file = e.dataTransfer.files[0]
        if (file) setSelectedFile(file)
    }, [])

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal card" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header"><h2>Import Leads</h2><button className="btn btn-ghost btn-sm" onClick={onClose}><X size={20} /></button></div>
                <div className="modal-body">
                    {!result ? (
                        <div className={`drop-zone ${isDragging ? 'dragging' : ''}`} onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }} onDragLeave={() => setIsDragging(false)} onDrop={handleDrop} onClick={() => fileInputRef.current?.click()}>
                            <input type="file" ref={fileInputRef} onChange={(e) => e.target.files?.[0] && setSelectedFile(e.target.files[0])} hidden />
                            <p>{selectedFile ? selectedFile.name : 'Select or drop CSV file'}</p>
                        </div>
                    ) : (
                        <div className="import-results"><h3>Imported: {result.created}</h3><button className="btn btn-primary" onClick={onSuccess}>Done</button></div>
                    )}
                </div>
                <div className="modal-actions">
                    {!result && <button className="btn btn-primary" disabled={!selectedFile} onClick={() => selectedFile && uploadMutation.mutate(selectedFile)}>Upload</button>}
                </div>
            </div>
        </div>
    )
}

function EditLeadModal({ lead, onClose, onSuccess }: { lead: Lead; onClose: () => void; onSuccess: () => void }) {
    const [formData, setFormData] = useState({ ...lead })
    const updateMutation = useMutation({
        mutationFn: (data: Partial<Lead>) => leadsApi.update(lead.id, data),
        onSuccess: () => {
            debugApi.terminalLog(`Lead ${lead.id} updated`)
            onSuccess()
        }
    })

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal card" style={{ maxWidth: '600px' }} onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <h2><Edit2 size={20} /> Edit Lead</h2>
                    <button className="btn btn-ghost btn-sm" onClick={onClose}><X size={20} /></button>
                </div>
                <form className="modal-form" onSubmit={(e) => { e.preventDefault(); updateMutation.mutate(formData) }}>
                    <div className="form-group">
                        <label>Company Name *</label>
                        <input className="input" required value={formData.company_name} onChange={e => setFormData({ ...formData, company_name: e.target.value })} />
                    </div>

                    <div className="form-group">
                        <label>Company Domain *</label>
                        <input className="input" required value={formData.company_domain} onChange={e => setFormData({ ...formData, company_domain: e.target.value })} />
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                        <div className="form-group">
                            <label>First Name</label>
                            <input className="input" value={formData.first_name || ''} onChange={e => setFormData({ ...formData, first_name: e.target.value })} />
                        </div>
                        <div className="form-group">
                            <label>Last Name</label>
                            <input className="input" value={formData.last_name || ''} onChange={e => setFormData({ ...formData, last_name: e.target.value })} />
                        </div>
                    </div>

                    <div className="form-group">
                        <label>Email *</label>
                        <input className="input" type="email" required value={formData.email} onChange={e => setFormData({ ...formData, email: e.target.value })} />
                    </div>

                    <div className="form-group">
                        <label>LinkedIn URL</label>
                        <input className="input" value={formData.linkedin_url || ''} onChange={e => setFormData({ ...formData, linkedin_url: e.target.value })} />
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                        <div className="form-group">
                            <label>Industry</label>
                            <input className="input" value={formData.industry || ''} onChange={e => setFormData({ ...formData, industry: e.target.value })} />
                        </div>
                        <div className="form-group">
                            <label>Mobile</label>
                            <input className="input" value={formData.mobile || ''} onChange={e => setFormData({ ...formData, mobile: e.target.value })} />
                        </div>
                    </div>

                    <div className="form-group">
                        <label>Status</label>
                        <input
                            className="input"
                            value={formData.status ? (formData.status.charAt(0).toUpperCase() + formData.status.slice(1)) : ''}
                            disabled
                            title="Status is managed by the system"
                        />
                    </div>

                    <div className="modal-actions">
                        <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
                        <button type="submit" className="btn btn-primary" disabled={updateMutation.isPending}>Save Changes</button>
                    </div>
                </form>
            </div>
        </div>
    )
}
