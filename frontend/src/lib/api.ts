import axios from 'axios'

const api = axios.create({
    baseURL: '/api/v1',
    headers: {
        'Content-Type': 'application/json',
    },
})

// Types
export interface Lead {
    id: string
    company_name: string
    company_domain: string
    email: string
    first_name?: string
    last_name?: string
    persona?: string
    region?: string
    industry?: string
    linkedin_url?: string
    title?: string
    mobile?: string
    status: string
    composite_score?: number
    fit_score?: number
    readiness_score?: number
    intent_score?: number
    risk_level?: string
    personalization_mode?: string
    num_followups?: number
    followup_delay_days?: number
    has_replied?: boolean
    created_at: string
    researched_at?: string
}

export interface Draft {
    id: string
    lead_id: string
    campaign_id?: string
    touch_number: number
    subject_options: string[]
    selected_subject?: string
    body: string
    status: string
    strategy?: Record<string, any>
    evidence?: Record<string, any>
    personalization_mode?: string
    created_at: string
    approved_at?: string
    lead_name?: string
    lead_company?: string
    lead_email?: string
}

export interface Sequence {
    id: string
    external_id?: string
    name: string
    description?: string
    status: string
    target_industry?: string
    target_persona?: string
    sequence_touches: number
    touch_delays?: number[]
    created_at: string
    total_leads?: number
    active_leads?: number
    completed_leads?: number
}

// Backward compatibility alias
export type Campaign = Sequence

export interface OverviewMetrics {
    total_leads: number
    leads_researched: number
    leads_qualified: number
    leads_in_sequence: number
    leads_contacted: number
    leads_replied: number
    active_campaigns: number
    pending_approvals: number
    emails_sent_7d: number
    open_rate_7d?: number
    reply_rate_7d?: number
}

export interface BulkImportResult {
    created: number
    skipped: number
    errors: Array<{ row?: number; index?: number; error: string }>
}

export interface ReceivedEmail {
    id: string
    to: string[]
    from: string
    created_at: string
    subject: string
    bcc: string[]
    cc: string[]
    reply_to: string[]
    message_id: string
    attachments: any[]
}

export interface ReceivedEmailList {
    object: string
    has_more: boolean
    data: ReceivedEmail[]
}

export interface ReceivedEmailDetail extends ReceivedEmail {
    text_body?: string
    html_body?: string
    text?: string
    html?: string
    headers?: Record<string, any>
}

// API functions
export const leadsApi = {
    list: async (params?: {
        page?: number
        status?: string
        search?: string
        min_score?: number
    }) => {
        const { data } = await api.get('/leads', { params })
        return data
    },

    get: async (id: string) => {
        const { data } = await api.get(`/leads/${id}`)
        return data
    },

    create: async (lead: Partial<Lead>) => {
        const { data } = await api.post('/leads', lead)
        return data
    },

    update: async (id: string, updates: Partial<Lead>) => {
        const { data } = await api.patch(`/leads/${id}`, updates)
        return data
    },

    delete: async (id: string) => {
        await api.delete(`/leads/${id}`)
    },

    triggerResearch: async (id: string, forceRefresh = true) => {
        const { data } = await api.post(`/leads/${id}/research`, null, {
            params: { force_refresh: forceRefresh }
        })
        return data
    },

    getIntelligence: async (id: string) => {
        const { data } = await api.get(`/leads/${id}/intelligence`)
        return data
    },

    bulkImport: async (file: File): Promise<BulkImportResult> => {
        const formData = new FormData()
        formData.append('file', file)
        const { data } = await api.post('/leads/upload', formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        })
        return data
    },
}

export const draftsApi = {
    list: async (params?: {
        page?: number
        status?: string
        campaign_id?: string
    }) => {
        const { data } = await api.get('/drafts', { params })
        return data
    },

    get: async (id: string) => {
        const { data } = await api.get(`/drafts/${id}`)
        return data
    },

    generate: async (request: {
        lead_ids: string[]
        campaign_id?: string
        touch_number?: number
        personalization_mode?: string
    }) => {
        const { data } = await api.post('/drafts/generate', request)
        return data
    },

    approve: async (id: string, request: {
        selected_subject: string
        approved_by: string
        scheduled_send_at?: string
    }) => {
        const { data } = await api.post(`/drafts/${id}/approve`, request)
        return data
    },

    reject: async (id: string, reason: string) => {
        const { data } = await api.post(`/drafts/${id}/reject`, { rejection_reason: reason })
        return data
    },

    regenerate: async (id: string, request?: {
        strategy_override?: string
        personalization_mode?: string
    }) => {
        const { data } = await api.post(`/drafts/${id}/regenerate`, request || {})
        return data
    },

    update: async (id: string, request: {
        subject?: string
        body?: string
    }) => {
        const { data } = await api.patch(`/drafts/${id}`, request)
        return data
    },

    bulkApprove: async (request: {
        draft_ids: string[]
        approved_by: string
    }) => {
        const { data } = await api.post('/drafts/bulk-approve', request)
        return data
    },
}

export const inSequenceApi = {
    list: async (params?: { page?: number; status?: string; type?: 'user' | 'system' | 'all' }) => {
        const { data } = await api.get('/in-sequence', { params })
        return data
    },

    get: async (id: string) => {
        const { data } = await api.get(`/in-sequence/${id}`)
        return data
    },

    getLeads: async (id: string, status?: string) => {
        const { data } = await api.get(`/in-sequence/${id}/leads`, { params: { status } })
        return data
    },

    create: async (campaign: Partial<Campaign>) => {
        const { data } = await api.post('/in-sequence', campaign)
        return data
    },

    update: async (id: string, updates: Partial<Campaign>) => {
        const { data } = await api.patch(`/in-sequence/${id}`, updates)
        return data
    },

    addLeads: async (id: string, leadIds: string[]) => {
        const { data } = await api.post(`/in-sequence/${id}/leads`, { lead_ids: leadIds })
        return data
    },

    start: async (id: string) => {
        const { data } = await api.post(`/in-sequence/${id}/start`)
        return data
    },

    pause: async (id: string) => {
        const { data } = await api.post(`/in-sequence/${id}/pause`)
        return data
    },

    delete: async (id: string) => {
        await api.delete(`/in-sequence/${id}`)
    },

    triggerFollowup: async (campaignId: string, leadId: string) => {
        const { data } = await api.post(`/in-sequence/${campaignId}/leads/${leadId}/trigger`)
        return data
    },

    approveFollowup: async (campaignId: string, leadId: string, request: {
        draft_id: string
        subject: string
        body: string
    }) => {
        const { data } = await api.post(`/in-sequence/${campaignId}/leads/${leadId}/approve`, request)
        return data
    },
}

export const analyticsApi = {
    overview: async (): Promise<OverviewMetrics> => {
        const { data } = await api.get('/analytics/overview')
        return data
    },

    campaign: async (id: string) => {
        const { data } = await api.get(`/analytics/in-sequence/${id}`)
        return data
    },

    templates: async () => {
        const { data } = await api.get('/analytics/templates')
        return data
    },

    funnel: async () => {
        const { data } = await api.get('/analytics/funnel')
        return data
    },
}

export const researchApi = {
    analyzeWebsite: async (url: string, forceRefresh = false) => {
        const { data } = await api.post('/research/analyze-website', { url, force_refresh: forceRefresh })
        return data
    },

    runResearch: async (leadId: string, options?: {
        include_linkedin?: boolean
        include_google?: boolean
    }) => {
        const { data } = await api.post(`/research/lead/${leadId}`, options || {
            include_linkedin: true,
            include_google: true,
        })
        return data
    },
}

export const templatesApi = {
    list: async (params?: { type?: string; active_only?: boolean }) => {
        const { data } = await api.get('/templates', { params })
        return data
    },

    create: async (template: {
        name: string
        type: string
        touch_number: number
        subject_template: string
        body_template: string
    }) => {
        const { data } = await api.post('/templates', template)
        return data
    },

    update: async (id: string, updates: Partial<{ name: string; is_active: boolean }>) => {
        const { data } = await api.patch(`/templates/${id}`, updates)
        return data
    },

    seed: async () => {
        const { data } = await api.post('/templates/seed')
        return data
    },
}

export const emailsApi = {
    listReceived: async (): Promise<ReceivedEmailList> => {
        const { data } = await api.get('/emails/received')
        return data
    },

    getReceived: async (emailId: string): Promise<ReceivedEmailDetail> => {
        const { data } = await api.get(`/emails/received/${emailId}`)
        return data
    },

    sendReply: async (leadId: string, subject: string, body: string) => {
        const { data } = await api.post('/emails/send-reply', null, {
            params: { lead_id: leadId, subject, body }
        })
        return data
    },
}

export const webhooksApi = {
    logManualReply: async (leadId: string, content: string, subject?: string) => {
        const { data } = await api.post('/webhooks/manual-reply-log', {
            lead_id: leadId,
            content,
            subject,
        }, {
            params: { lead_id: leadId, content, subject } // Passed in params for FastAPI's simple query parsing
        })
        return data
    },
}

export const debugApi = {
    terminalLog: async (message: string, level: string = 'info') => {
        try {
            await api.post('/debug/log', { message, level })
        } catch (e) {
            // Silently fail if debug logging fails to avoid recursion or annoying user
        }
    }
}

export default api
