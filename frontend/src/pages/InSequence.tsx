
import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { inSequenceApi, leadsApi, emailsApi, Campaign, Lead, Draft } from '../lib/api'
import { Play, Pause, Rocket, Hand, Search, Plus, Edit2, Check, X, Zap, ChevronRight, Send, Mail, Users, CheckCircle } from 'lucide-react'
import './Campaigns.css'
import 'react-quill/dist/quill.snow.css'
import ReactQuill, { Quill } from 'react-quill'

// Register fonts with Quill
const Font = Quill.import('formats/font')
Font.whitelist = ['arial', 'georgia', 'times-roman', 'verdana', 'trebuchet', 'garamond']
Quill.register(Font, true)

// Quill editor modules configuration with fonts
const quillModules = {
    toolbar: [
        [{ 'font': ['arial', 'georgia', 'times-roman', 'verdana', 'trebuchet', 'garamond'] }],
        [{ 'size': ['small', false, 'large'] }],
        ['bold', 'italic', 'underline'],
        [{ 'list': 'ordered' }, { 'list': 'bullet' }],
        [{ 'align': [] }],
        ['link'],
        ['clean']
    ],
}

const quillFormats = [
    'font', 'size',
    'bold', 'italic', 'underline',
    'list', 'bullet',
    'align',
    'link'
]

const STATUS_COLORS: Record<string, string> = {
    draft: 'neutral',
    active: 'success',
    paused: 'warning',
    completed: 'info',
}

export default function InSequence() {
    const queryClient = useQueryClient()

    // Trigger Draft State
    const [selectedSequenceLead, setSelectedSequenceLead] = useState<Lead | null>(null)
    const [viewingEmailsId, setViewingEmailsId] = useState<string | null>(null)
    const [summaryModalOpen, setSummaryModalOpen] = useState(false)
    const [triggerDraft, setTriggerDraft] = useState<Draft | null>(null)
    const [draftBody, setDraftBody] = useState('')
    const [draftSubject, setDraftSubject] = useState('')
    const [isTriggering, setIsTriggering] = useState(false)

    // Config editing state
    const [editForm, setEditForm] = useState({
        sequence_touches: 3,
        touch_delays: '3',
        isEditing: false
    })
    const [showCompleted, setShowCompleted] = useState(false)

    // Fetch System Campaigns
    const { data: campaignsData } = useQuery({
        queryKey: ['campaigns', 'system'],
        queryFn: () => inSequenceApi.list({ type: 'system' }),
    })

    // Derived default campaign
    const campaigns: Campaign[] = campaignsData?.items || []
    const defaultCampaign = campaigns.find(c => c.external_id === 'DEFAULT-FOLLOWUP') || campaigns[0]

    // Fetch Leads currently IN SEQUENCE (global list)
    const { data: leadsData, isLoading: isLoadingSequence } = useQuery({
        queryKey: ['leads', 'in_sequence'],
        queryFn: async () => {
            const inProgress = await leadsApi.list({ status: 'inprogress' });
            const completed = await leadsApi.list({ status: 'completed' });
            return {
                items: [...(inProgress.items || []), ...(completed.items || [])],
                total: (inProgress.total || 0) + (completed.total || 0)
            };
        },
    })

    const leadsInSequence = leadsData?.items || []

    // Metrics for the top bar
    const stats = [
        { label: 'Active in Sequence', value: leadsInSequence.filter((l: Lead) => l.status === 'sequencing').length, icon: Zap, color: 'text-primary' },
        { label: 'Ready for Follow-up', value: leadsInSequence.filter((l: Lead) => l.status === 'contacted').length, icon: Mail, color: 'text-warning' },
        { label: 'Completed', value: leadsInSequence.filter((l: Lead) => l.status === 'completed').length, icon: CheckCircle, color: 'text-success' },
        { label: 'Total Enrolled', value: leadsInSequence.length, icon: Users, color: 'text-secondary' },
    ]

    // Sync form with campaign
    useEffect(() => {
        if (defaultCampaign) {
            setEditForm(prev => ({
                ...prev,
                sequence_touches: defaultCampaign.sequence_touches || 3,
                touch_delays: String(defaultCampaign.touch_delays?.[0] || '3'),
            }))
        }
    }, [defaultCampaign])

    const activeLeads = leadsInSequence.filter((l: Lead) => l.status === 'sequencing' || l.status === 'contacted')
    const completedLeads = leadsInSequence.filter((l: Lead) => ['completed', 'replied', 'converted', 'disqualified'].includes(l.status))

    const leadsToShow = showCompleted ? completedLeads : activeLeads

    const updateCampaignMutation = useMutation({
        mutationFn: ({ id, data }: { id: string; data: Partial<Campaign> }) =>
            inSequenceApi.update(id, data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['campaigns'] })
            queryClient.invalidateQueries({ queryKey: ['campaign', defaultCampaign?.id] })
        },
    })

    const triggerFollowupMutation = useMutation({
        mutationFn: async ({ campaignId, leadId }: { campaignId: string, leadId: string }) => {
            try {
                return await inSequenceApi.triggerFollowup(campaignId, leadId)
            } catch (err: any) {
                if (err.response?.status === 404) {
                    // Auto-enroll if not in campaign
                    await inSequenceApi.addLeads(campaignId, [leadId])
                    return await inSequenceApi.triggerFollowup(campaignId, leadId)
                }
                throw err
            }
        },
        onSuccess: (data) => {
            setTriggerDraft(data)
            setDraftSubject(data.selected_subject || data.subject_options?.[0] || '')
            setDraftBody(data.body)
            setIsTriggering(false)
        },
        onError: (error: any) => {
            setIsTriggering(false)
            alert(error.response?.data?.detail || 'Failed to trigger follow-up draft.')
        }
    })

    const approveFollowupMutation = useMutation({
        mutationFn: ({ campaignId, leadId, request }: { campaignId: string, leadId: string, request: any }) =>
            inSequenceApi.approveFollowup(campaignId, leadId, request),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['campaign'] })
            queryClient.invalidateQueries({ queryKey: ['leads'] })
            setSummaryModalOpen(false)
            setSelectedSequenceLead(null)
            setTriggerDraft(null)
            alert('Follow-up email sequence initiated successfully!')
        }
    })

    const handleRowClick = (lead: Lead) => {
        if (!defaultCampaign) return
        setSelectedSequenceLead(lead)
        setTriggerDraft(null) // Reset while loading
        setIsTriggering(true)
        triggerFollowupMutation.mutate({ campaignId: defaultCampaign.id, leadId: lead.id })
    }

    const handleApproveClick = () => {
        setSummaryModalOpen(true)
    }

    const handleConfirmSend = () => {
        if (!defaultCampaign || !selectedSequenceLead || !triggerDraft) return
        approveFollowupMutation.mutate({
            campaignId: defaultCampaign.id,
            leadId: selectedSequenceLead.id,
            request: {
                draft_id: triggerDraft.id,
                subject: draftSubject,
                body: draftBody
            }
        })
    }

    const saveEditing = async (campaignId: string) => {
        const touches = parseInt(String(editForm.sequence_touches)) || 3
        const delayInput = parseInt(String(editForm.touch_delays)) || 3
        const finalDelays = Array(touches).fill(delayInput)

        await updateCampaignMutation.mutateAsync({
            id: campaignId,
            data: {
                sequence_touches: touches,
                touch_delays: finalDelays
            }
        })
    }

    return (
        <div className="campaigns-page animate-fadeIn space-y-8">
            <div className="page-header">
                <div>
                    <h1>In Sequence</h1>
                    <p className="text-secondary text-sm">Monitor and drive your automated follow-up sequences.</p>
                </div>
            </div>

            {/* Stats Overview */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {stats.map((stat, i) => (
                    <div key={i} className="card flex items-center gap-4">
                        <div className={`p-3 rounded-full bg-primary/10 ${stat.color}`}>
                            <stat.icon size={24} />
                        </div>
                        <div>
                            <p className="text-xs text-secondary uppercase font-bold tracking-wider">{stat.label}</p>
                            <p className="text-2xl font-bold">{stat.value}</p>
                        </div>
                    </div>
                ))}
            </div>

            {/* Leads in Sequence (Main View) */}
            <div className="card">
                <div className="card-header border-b border-border pb-4 mb-4 flex justify-between items-center">
                    <div>
                        <h3>{showCompleted ? 'Sequence History' : 'Active Sequence Queue'}</h3>
                        <div className="flex gap-2">
                            <span className="badge badge-success">{defaultCampaign?.name || 'Default Campaign'}</span>
                        </div>
                    </div>
                    <button
                        className={`btn btn-sm ${showCompleted ? 'btn-primary' : 'btn-secondary'}`}
                        onClick={() => setShowCompleted(!showCompleted)}
                    >
                        {showCompleted ? 'Show Active Queue' : 'Show Completed/History'}
                    </button>
                </div>

                <div className="sequence-list">
                    <table className="table w-full">
                        <thead>
                            <tr className="text-left text-sm text-secondary bg-bg-secondary">
                                <th className="p-3">Company</th>
                                <th className="p-3">Contact</th>
                                <th className="p-3">Status</th>
                                <th className="p-3">Progress</th>
                                <th className="p-3 text-right">Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {isLoadingSequence ? (
                                <tr>
                                    <td colSpan={5} className="p-8 text-center text-secondary">Loading your sequence...</td>
                                </tr>
                            ) : leadsToShow.length === 0 ? (
                                <tr>
                                    <td colSpan={5} className="p-12 text-center">
                                        <div className="text-secondary mb-4 opacity-50"><Mail size={48} className="mx-auto" /></div>
                                        <p className="text-secondary">
                                            {showCompleted ? 'No completed sequences yet.' : 'No leads currently in the sequencing flow.'}
                                        </p>
                                        <p className="text-xs text-muted mt-1">
                                            {showCompleted ? 'Check back later.' : 'Enroll leads from the Leads page to see them here.'}
                                        </p>
                                    </td>
                                </tr>
                            ) : (
                                leadsToShow.map((lead: Lead) => (
                                    <tr
                                        key={lead.id}
                                        className={`border-b border-border hover:bg-bg-secondary transition-colors cursor-pointer ${selectedSequenceLead?.id === lead.id ? 'bg-primary/5' : ''}`}
                                        onClick={() => handleRowClick(lead)}
                                    >
                                        <td className="p-3">
                                            <div className="font-medium text-white">{lead.company_name}</div>
                                            <div className="text-[10px] text-muted">{lead.industry || 'Lead'}</div>
                                        </td>
                                        <td className="p-3">
                                            <div className="font-bold text-sm">{lead.first_name} {lead.last_name}</div>
                                            <div className="text-xs text-secondary">{lead.email}</div>
                                        </td>
                                        <td className="p-3">
                                            <span className={`badge badge-${lead.status === 'sequencing' ? 'info' : 'warning'} text-[10px]`}>
                                                {lead.status === 'sequencing' ? 'ACTIVE' : 'READY'}
                                            </span>
                                            <div className="text-[10px] mt-1 text-secondary uppercase font-bold">
                                                {lead.status === 'sequencing' ? 'In Sync' : 'Wait Trigger'}
                                            </div>
                                        </td>
                                        <td className="p-3">
                                            <span className="text-sm font-medium">Touch {lead.num_followups ? lead.num_followups + 1 : 1}</span>
                                            <div className="w-24 h-1 bg-border rounded-full mt-1 overflow-hidden">
                                                <div
                                                    className="h-full bg-primary"
                                                    style={{ width: `${((lead.num_followups || 0) / (defaultCampaign?.sequence_touches || 3)) * 100}%` }}
                                                />
                                            </div>
                                        </td>
                                        <td className="p-3 text-right">
                                            <div className="flex justify-end gap-2">
                                                <button
                                                    className="btn btn-ghost btn-sm"
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        setViewingEmailsId(lead.id);
                                                    }}
                                                    title="View Email History"
                                                >
                                                    <Mail size={16} />
                                                </button>
                                                <button className="btn btn-ghost btn-sm">
                                                    <ChevronRight size={16} />
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Follow-up Preview Panel */}
            {selectedSequenceLead && (
                <div id="followup-preview" className="card border-t-4 border-t-primary animate-slideUp shadow-xl">
                    <div className="flex justify-between items-center mb-6">
                        <div>
                            <h3 className="flex items-center">
                                <Zap size={20} className="text-primary mr-2" />
                                Sequence Orchestrator: {selectedSequenceLead.company_name}
                            </h3>
                            <p className="text-sm text-secondary">Verify and edit the follow-up template for {selectedSequenceLead.first_name}.</p>
                        </div>
                        <button onClick={() => setSelectedSequenceLead(null)} className="IconButton">
                            <X size={20} />
                        </button>
                    </div>

                    {isTriggering && !triggerDraft ? (
                        <div className="p-12 text-center">
                            <div className="animate-spin inline-block w-8 h-8 border-2 border-primary border-t-transparent rounded-full mb-4"></div>
                            <p className="text-secondary">Generating personalized follow-up...</p>
                        </div>
                    ) : (
                        <div className="space-y-6">
                            <div className="space-y-2">
                                <label className="text-xs font-bold text-secondary uppercase tracking-wider">Email Subject</label>
                                <input
                                    className="input w-full"
                                    value={draftSubject}
                                    onChange={(e) => setDraftSubject(e.target.value)}
                                    placeholder="Enter email subject..."
                                />
                            </div>

                            <div className="space-y-2">
                                <label className="text-xs font-bold text-secondary uppercase tracking-wider">Email Content</label>
                                <ReactQuill
                                    theme="snow"
                                    value={draftBody}
                                    onChange={setDraftBody}
                                    modules={quillModules}
                                    formats={quillFormats}
                                    className="bg-bg-primary rounded-md"
                                    placeholder="Write your email here..."
                                />
                                <div className="flex justify-between items-center text-[10px] mt-1">
                                    <span className="text-secondary italic">Using AI-Generated Follow-up Template</span>
                                </div>
                            </div>

                            <div className="pt-4 border-t border-border flex justify-end">
                                <button
                                    className="btn btn-primary btn-lg"
                                    onClick={handleApproveClick}
                                    disabled={!triggerDraft}
                                >
                                    <Send size={18} className="mr-2" />
                                    Approve and Send Followup Emails
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Sequence Summary Modal (Popup) */}
            {summaryModalOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-md p-4">
                    <div className="card w-full max-w-md animate-scaleIn shadow-2xl border border-primary/20">
                        <div className="text-center mb-6">
                            <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-4">
                                <Rocket className="text-primary" size={32} />
                            </div>
                            <h2 className="text-2xl font-bold">Initiate Sequence</h2>
                            <p className="text-secondary mt-2">Starting a follow-up sequence for <strong>{selectedSequenceLead?.company_name}</strong>.</p>
                        </div>

                        <div className="bg-bg-secondary rounded-xl p-4 mb-8 space-y-4">
                            <div className="flex justify-between items-center pb-3 border-b border-border">
                                <span className="text-secondary">Total Follow-ups</span>
                                <div className="flex items-center gap-2">
                                    <input
                                        type="number"
                                        className="input w-20 text-center py-1 h-8"
                                        value={editForm.sequence_touches}
                                        min={1}
                                        max={10}
                                        onChange={(e) => setEditForm({ ...editForm, sequence_touches: parseInt(e.target.value) || 3 })}
                                    />
                                    <span className="font-bold text-sm">Emails</span>
                                </div>
                            </div>
                            <div className="flex justify-between items-center pb-3 border-b border-border">
                                <span className="text-secondary">Sending Interval</span>
                                <div className="flex flex-col items-end">
                                    <div className="flex items-center gap-2">
                                        <input
                                            type="number"
                                            className="input w-20 text-center py-1 h-8"
                                            value={editForm.touch_delays}
                                            min={1}
                                            max={60}
                                            onChange={(e) => setEditForm({ ...editForm, touch_delays: e.target.value })}
                                        />
                                        <span className="font-bold text-sm">Minutes</span>
                                    </div>
                                    <span className="text-[10px] text-secondary mt-1">
                                        (Interval between emails)
                                    </span>
                                </div>
                            </div>
                            <div className="flex justify-between items-center">
                                <span className="text-secondary">Auto-Stop Condition</span>
                                <span className="font-bold text-success">Lead Replies</span>
                            </div>
                        </div>

                        <div className="flex flex-col gap-3">
                            <button
                                className="btn btn-primary w-full py-4 text-lg"
                                onClick={async () => {
                                    if (defaultCampaign) {
                                        // 1. Save Config
                                        await saveEditing(defaultCampaign.id);
                                        // 2. Start Sequence
                                        handleConfirmSend();
                                    }
                                }}
                                disabled={approveFollowupMutation.isPending || updateCampaignMutation.isPending}
                            >
                                {(approveFollowupMutation.isPending || updateCampaignMutation.isPending) ? 'Initiating...' : 'Confirm and Start Sequence'}
                            </button>
                            <button
                                className="btn btn-secondary w-full"
                                onClick={() => setSummaryModalOpen(false)}
                            >
                                Cancel
                            </button>
                        </div>

                        <p className="text-[10px] text-center text-secondary mt-6">
                            The first email will be sent immediately. Subsequent emails will be sent automatically if no reply is received.
                        </p>
                    </div>
                </div>
            )}
            {viewingEmailsId && (
                <EmailsPanel
                    leadId={viewingEmailsId}
                    onClose={() => setViewingEmailsId(null)}
                />
            )}
        </div>
    )
}

function EmailTimelineItem({ item }: { item: any }) {
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

    let content = item.content;
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
    const { data: leadData, isLoading: isLoadingLead } = useQuery({
        queryKey: ['intelligence', leadId],
        queryFn: () => leadsApi.getIntelligence(leadId),
    })

    const { data: receivedEmails, isLoading: isLoadingEmails } = useQuery({
        queryKey: ['received-emails'],
        queryFn: emailsApi.listReceived,
    })

    if (isLoadingLead || isLoadingEmails) return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal card" onClick={(e) => e.stopPropagation()}>
                <div className="loading-state"><div className="spinner" /><p>Loading emails...</p></div>
            </div>
        </div>
    )

    if (!leadData) return null;

    const leadEmail = leadData.lead?.email?.toLowerCase();
    const relevantReceived = (receivedEmails as any)?.data?.filter((email: any) =>
        (email.from && email.from.toLowerCase().includes(leadEmail)) ||
        (email.to && email.to.some((t: string) => t.toLowerCase().includes(leadEmail))) ||
        (email.from && leadEmail && email.from.toLowerCase().includes(leadEmail))
    ) || [];

    const sentEvents = leadData.events?.filter((e: any) => e.event_type === 'sent') || [];

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
        </div>
    )
}
