import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { draftsApi, Draft } from '../lib/api'
import 'react-quill/dist/quill.snow.css'
import {
    Check,
    X,
    RefreshCw,
    ChevronLeft,
    ChevronRight,
    Eye,
    Lightbulb,
    Target,
    AlertTriangle,
    Clock,
    Save,
    Edit3,
} from 'lucide-react'
import './Drafts.css'

const STATUS_COLORS: Record<string, string> = {
    pending: 'warning',
    approved: 'success',
    rejected: 'error',
    sent: 'info',
}

// Professional font options
const FONT_OPTIONS = [
    { value: 'arial', label: 'Arial' },
    { value: 'georgia', label: 'Georgia' },
    { value: 'times-roman', label: 'Times New Roman' },
    { value: 'verdana', label: 'Verdana' },
    { value: 'trebuchet', label: 'Trebuchet MS' },
    { value: 'garamond', label: 'Garamond' },
]



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

// Register fonts with Quill
import ReactQuill, { Quill } from 'react-quill'
const Font = Quill.import('formats/font')
Font.whitelist = ['arial', 'georgia', 'times-roman', 'verdana', 'trebuchet', 'garamond']
Quill.register(Font, true)

export default function Drafts() {
    const queryClient = useQueryClient()
    const [page, setPage] = useState(1)
    const [statusFilter, setStatusFilter] = useState('pending')
    const [selectedDraft, setSelectedDraft] = useState<Draft | null>(null)

    // Editing state
    const [editedSubject, setEditedSubject] = useState<string>('')
    const [editedBody, setEditedBody] = useState<string>('')
    const [isEdited, setIsEdited] = useState(false)
    const [useCustomSubject, setUseCustomSubject] = useState(false)
    const [showRejectModal, setShowRejectModal] = useState(false)
    const [rejectReason, setRejectReason] = useState('')


    const { data, isLoading } = useQuery({
        queryKey: ['drafts', page, statusFilter],
        queryFn: () => draftsApi.list({ page, status: statusFilter || undefined }),
    })

    // Update mutation for saving edits
    const updateMutation = useMutation({
        mutationFn: ({ id, subject, body }: { id: string; subject?: string; body?: string }) =>
            draftsApi.update(id, { subject, body }),
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ['drafts'] })
            setSelectedDraft(data)
            setIsEdited(false)
        },
    })

    const approveMutation = useMutation({
        mutationFn: ({ id, subject }: { id: string; subject: string }) =>
            draftsApi.approve(id, { selected_subject: subject, approved_by: 'user' }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['drafts'] })
            setSelectedDraft(null)
        },
    })

    const rejectMutation = useMutation({
        mutationFn: ({ id, reason }: { id: string; reason: string }) =>
            draftsApi.reject(id, reason),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['drafts'] })
            setSelectedDraft(null)
            setShowRejectModal(false)
            setRejectReason('')
        },
    })

    const regenerateMutation = useMutation({
        mutationFn: (id: string) => draftsApi.regenerate(id),
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ['drafts'] })
            setSelectedDraft(data)
            setEditedBody(data.body || '')
            setEditedSubject(data.selected_subject || data.subject_options?.[0] || '')
            setIsEdited(false)
        },
    })

    const drafts: Draft[] = data?.items || []
    const totalPages = data?.pages || 1

    const openDraft = (draft: Draft) => {
        setSelectedDraft(draft)
        setEditedSubject(draft.selected_subject || draft.subject_options?.[0] || '')
        setEditedBody(draft.body || '')
        setUseCustomSubject(!!draft.selected_subject && !draft.subject_options?.includes(draft.selected_subject))
        setIsEdited(false)
    }

    // Track changes
    useEffect(() => {
        if (selectedDraft) {
            const originalSubject = selectedDraft.selected_subject || selectedDraft.subject_options?.[0] || ''
            const originalBody = selectedDraft.body || ''
            setIsEdited(editedSubject !== originalSubject || editedBody !== originalBody)
        }
    }, [editedSubject, editedBody, selectedDraft])

    const handleSave = () => {
        if (selectedDraft && isEdited) {
            updateMutation.mutate({
                id: selectedDraft.id,
                subject: editedSubject,
                body: editedBody,
            })
        }
    }

    const handleApprove = () => {
        if (selectedDraft) {
            // Save first if edited, then approve
            if (isEdited) {
                updateMutation.mutate({
                    id: selectedDraft.id,
                    subject: editedSubject,
                    body: editedBody,
                }, {
                    onSuccess: () => {
                        approveMutation.mutate({ id: selectedDraft.id, subject: editedSubject })
                    }
                })
            } else {
                approveMutation.mutate({ id: selectedDraft.id, subject: editedSubject })
            }
        }
    }

    const handleReject = () => {
        if (selectedDraft && rejectReason.trim()) {
            rejectMutation.mutate({ id: selectedDraft.id, reason: rejectReason })
        }
    }

    return (
        <div className="drafts-page animate-fadeIn">
            <div className="page-header">
                <div>
                    <h1>Draft Approvals</h1>
                    <p className="text-secondary">Review, edit, and approve email drafts</p>
                </div>
            </div>

            {/* Filters */}
            <div className="filters-bar">
                <div className="status-tabs">
                    {['pending', 'approved', 'rejected', ''].map((status) => (
                        <button
                            key={status}
                            className={`tab ${statusFilter === status ? 'tab-active' : ''}`}
                            onClick={() => setStatusFilter(status)}
                        >
                            {status || 'All'}
                            {status === 'pending' && data?.total > 0 && (
                                <span className="tab-badge">{data.total}</span>
                            )}
                        </button>
                    ))}
                </div>
            </div>

            <div className="drafts-layout">
                {/* Drafts List */}
                <div className="drafts-list card">
                    {isLoading ? (
                        <div className="loading-state">
                            <div className="spinner" />
                        </div>
                    ) : drafts.length === 0 ? (
                        <div className="empty-state">
                            <Clock size={48} />
                            <p>No drafts to review</p>
                        </div>
                    ) : (
                        <div className="draft-items">
                            {drafts.map((draft) => (
                                <div
                                    key={draft.id}
                                    className={`draft-item ${selectedDraft?.id === draft.id ? 'draft-item-selected' : ''}`}
                                    onClick={() => openDraft(draft)}
                                >
                                    <div className="draft-item-header">
                                        <span className="draft-company">{draft.lead_company}</span>
                                        <span className={`badge badge-${STATUS_COLORS[draft.status]}`}>
                                            {draft.status}
                                        </span>
                                    </div>
                                    <div className="draft-item-subject">
                                        {draft.subject_options?.[0] || 'No subject'}
                                    </div>
                                    <div className="draft-item-meta">
                                        <span>Touch {draft.touch_number}</span>
                                        <span>•</span>
                                        <span>{draft.lead_email}</span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Pagination */}
                    {totalPages > 1 && (
                        <div className="pagination">
                            <button
                                className="btn btn-ghost btn-sm"
                                onClick={() => setPage((p) => Math.max(1, p - 1))}
                                disabled={page === 1}
                            >
                                <ChevronLeft size={16} />
                            </button>
                            <span className="page-info">
                                {page} / {totalPages}
                            </span>
                            <button
                                className="btn btn-ghost btn-sm"
                                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                                disabled={page === totalPages}
                            >
                                <ChevronRight size={16} />
                            </button>
                        </div>
                    )}
                </div>

                {/* Draft Preview/Editor */}
                {selectedDraft ? (
                    <div className="draft-preview">
                        {/* Email Editor */}
                        <div className="card preview-card">
                            <div className="preview-header">
                                <h3>
                                    <Edit3 size={18} />
                                    Email Editor
                                </h3>
                                <div className="preview-actions">
                                    {isEdited && (
                                        <span className="edited-badge">Edited</span>
                                    )}
                                    <button
                                        className="btn btn-ghost btn-sm"
                                        onClick={() => regenerateMutation.mutate(selectedDraft.id)}
                                        disabled={regenerateMutation.isPending}
                                        title="Regenerate"
                                    >
                                        <RefreshCw size={16} className={regenerateMutation.isPending ? 'animate-spin' : ''} />
                                    </button>
                                </div>
                            </div>

                            <div className="preview-content">
                                <div className="preview-to">
                                    <strong>To:</strong> {selectedDraft.lead_name || selectedDraft.lead_email}
                                    &lt;{selectedDraft.lead_email}&gt;
                                </div>

                                {/* Subject Section */}
                                <div className="subject-section">
                                    <label className="text-sm font-medium">Subject Line:</label>

                                    <div className="subject-toggle">
                                        <label className="toggle-option">
                                            <input
                                                type="radio"
                                                name="subjectType"
                                                checked={!useCustomSubject}
                                                onChange={() => {
                                                    setUseCustomSubject(false)
                                                    setEditedSubject(selectedDraft.subject_options?.[0] || '')
                                                }}
                                            />
                                            <span>Choose from suggestions</span>
                                        </label>
                                        <label className="toggle-option">
                                            <input
                                                type="radio"
                                                name="subjectType"
                                                checked={useCustomSubject}
                                                onChange={() => setUseCustomSubject(true)}
                                            />
                                            <span>Custom subject</span>
                                        </label>
                                    </div>

                                    {useCustomSubject ? (
                                        <input
                                            type="text"
                                            className="input subject-input"
                                            value={editedSubject}
                                            onChange={(e) => setEditedSubject(e.target.value)}
                                            placeholder="Enter custom subject line..."
                                        />
                                    ) : (
                                        <div className="subject-list">
                                            {selectedDraft.subject_options?.map((subject, i) => (
                                                <label key={i} className="subject-option">
                                                    <input
                                                        type="radio"
                                                        name="subject"
                                                        value={subject}
                                                        checked={editedSubject === subject}
                                                        onChange={(e) => setEditedSubject(e.target.value)}
                                                    />
                                                    <span>{subject}</span>
                                                </label>
                                            ))}
                                        </div>
                                    )}
                                </div>


                                {/* Rich Text Editor */}
                                <div className="email-editor">
                                    <label className="text-sm font-medium">Email Body:</label>
                                    <ReactQuill
                                        theme="snow"
                                        value={editedBody}
                                        onChange={setEditedBody}
                                        modules={quillModules}
                                        formats={quillFormats}
                                        placeholder="Write your email..."
                                    />
                                </div>
                            </div>

                            {selectedDraft.status === 'pending' && (
                                <div className="preview-footer">
                                    <button
                                        className="btn btn-danger"
                                        onClick={() => setShowRejectModal(true)}
                                        disabled={rejectMutation.isPending}
                                    >
                                        <X size={18} />
                                        Reject
                                    </button>
                                    <div className="footer-right">
                                        {isEdited && (
                                            <button
                                                className="btn btn-secondary"
                                                onClick={handleSave}
                                                disabled={updateMutation.isPending}
                                            >
                                                <Save size={18} />
                                                {updateMutation.isPending ? 'Saving...' : 'Save Draft'}
                                            </button>
                                        )}
                                        <button
                                            className="btn btn-success"
                                            onClick={handleApprove}
                                            disabled={approveMutation.isPending || !editedSubject}
                                        >
                                            <Check size={18} />
                                            {approveMutation.isPending ? 'Approving...' : 'Approve & Send'}
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Evidence Panel */}
                        <div className="card evidence-panel">
                            <h3>Evidence & Strategy</h3>

                            <div className="evidence-section">
                                <div className="evidence-header">
                                    <Target size={16} />
                                    <span>Strategy</span>
                                </div>
                                <div className="evidence-content">
                                    <div className="evidence-item">
                                        <span className="evidence-label">Angle</span>
                                        <span className="evidence-value">{selectedDraft.strategy?.angle || '—'}</span>
                                    </div>
                                    <div className="evidence-item">
                                        <span className="evidence-label">CTA</span>
                                        <span className="evidence-value">{selectedDraft.strategy?.cta || '—'}</span>
                                    </div>
                                    <div className="evidence-item">
                                        <span className="evidence-label">Tone</span>
                                        <span className="evidence-value">{selectedDraft.strategy?.tone || '—'}</span>
                                    </div>
                                    <div className="evidence-item">
                                        <span className="evidence-label">Personalization</span>
                                        <span className="evidence-value">{selectedDraft.personalization_mode || '—'}</span>
                                    </div>
                                </div>
                            </div>

                            <div className="evidence-section">
                                <div className="evidence-header">
                                    <Lightbulb size={16} />
                                    <span>Pain Hypothesis</span>
                                </div>
                                <p className="evidence-text">
                                    {selectedDraft.strategy?.pain_hypothesis || 'No hypothesis available'}
                                </p>
                            </div>

                            {selectedDraft.evidence?.triggers && selectedDraft.evidence.triggers.length > 0 && (
                                <div className="evidence-section">
                                    <div className="evidence-header">
                                        <AlertTriangle size={16} />
                                        <span>Triggers Used</span>
                                    </div>
                                    <ul className="evidence-list">
                                        {selectedDraft.evidence.triggers.map((trigger: any, i: number) => (
                                            <li key={i}>
                                                <span className="trigger-type">{trigger.type}</span>
                                                <span className="trigger-summary">{trigger.summary}</span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                        </div>
                    </div>
                ) : (
                    <div className="draft-preview-empty card">
                        <Eye size={48} />
                        <p>Select a draft to preview and edit</p>
                    </div>
                )}
            </div>

            {/* Reject Modal */}
            {showRejectModal && (
                <div className="modal-overlay" onClick={() => setShowRejectModal(false)}>
                    <div className="modal reject-modal" onClick={(e) => e.stopPropagation()}>
                        <div className="modal-header">
                            <h2>Reject Draft</h2>
                            <button className="btn btn-ghost btn-sm" onClick={() => setShowRejectModal(false)}>
                                <X size={20} />
                            </button>
                        </div>
                        <div className="modal-body">
                            <label className="form-group">
                                <span>Reason for rejection:</span>
                                <textarea
                                    className="input reject-textarea"
                                    value={rejectReason}
                                    onChange={(e) => setRejectReason(e.target.value)}
                                    placeholder="Please provide a reason for rejecting this draft..."
                                    rows={4}
                                />
                            </label>
                        </div>
                        <div className="modal-actions">
                            <button className="btn btn-ghost" onClick={() => setShowRejectModal(false)}>
                                Cancel
                            </button>
                            <button
                                className="btn btn-danger"
                                onClick={handleReject}
                                disabled={!rejectReason.trim() || rejectMutation.isPending}
                            >
                                {rejectMutation.isPending ? 'Rejecting...' : 'Reject Draft'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
