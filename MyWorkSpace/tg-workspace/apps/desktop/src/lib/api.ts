import axios from 'axios'

const API_BASE_URL = 'http://127.0.0.1:8765/api'

export const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
})

// Workspaces
export const workspacesApi = {
    list: () => api.get('/workspaces/'),
    get: (id: number) => api.get(`/workspaces/${id}`),
    create: (data: { name: string; description?: string }) => api.post('/workspaces/', data),
    update: (id: number, data: { name: string; description?: string }) => api.put(`/workspaces/${id}`, data),
    delete: (id: number) => api.delete(`/workspaces/${id}`),
}

// Sources
export const sourcesApi = {
    list: (workspaceId: number) => api.get(`/sources/workspace/${workspaceId}`),
    uploadFile: (workspaceId: number, title: string, file: File) => {
        const formData = new FormData()
        formData.append('workspace_id', workspaceId.toString())
        formData.append('title', title)
        formData.append('file', file)
        return api.post('/sources/upload', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        })
    },
    classify: (sourceId: number) => api.post(`/sources/${sourceId}/classify`),
    delete: (id: number) => api.delete(`/sources/${id}`),
}

// Leads
export const leadsApi = {
    list: (workspaceId: number, params?: Record<string, any>) =>
        api.get(`/leads/workspace/${workspaceId}`, { params }),
    get: (id: number) => api.get(`/leads/${id}`),
    canContact: (id: number) => api.get(`/leads/${id}/can-contact`),
    updateStatus: (id: number, data: { status: string; lost_reason?: string; expected_revenue?: number }) =>
        api.put(`/leads/${id}/status`, data),
    updateDnc: (id: number, data: { do_not_contact: boolean; reason?: string }) =>
        api.put(`/leads/${id}/dnc`, data),
    getNotes: (id: number) => api.get(`/leads/${id}/notes`),
    addNote: (id: number, text: string) => api.post(`/leads/${id}/notes`, { text }),
    getTasks: (id: number) => api.get(`/leads/${id}/tasks`),
    addTask: (id: number, data: { type: string; title?: string; due_at: string }) =>
        api.post(`/leads/${id}/tasks`, data),
    stats: (workspaceId: number) => api.get(`/leads/stats/${workspaceId}`),
}

// Outreach
export const outreachApi = {
    history: (leadId: number) => api.get(`/outreach/lead/${leadId}`),
    createDraft: (data: { lead_id: number; message_text: string; template_id?: number }) =>
        api.post('/outreach/draft', data),
    generate: (data: { lead_id: number; template_id?: number }) =>
        api.post('/outreach/generate', data),
    markSent: (id: number) => api.post(`/outreach/${id}/mark-sent`),
    markReplied: (id: number) => api.post(`/outreach/${id}/mark-replied`),
    todayStats: () => api.get('/outreach/stats/today'),
    pendingFollowups: (workspaceId: number) => api.get('/outreach/pending-followups', { params: { workspace_id: workspaceId } }),
}

// Templates
export const templatesApi = {
    list: () => api.get('/templates/'),
    get: (id: number) => api.get(`/templates/${id}`),
    create: (data: { name: string; category?: string; text: string }) =>
        api.post('/templates/', data),
    update: (id: number, data: { name: string; category?: string; text: string }) =>
        api.put(`/templates/${id}`, data),
    delete: (id: number) => api.delete(`/templates/${id}`),
    seedDefaults: () => api.post('/templates/seed-defaults'),
}

// Settings
export const settingsApi = {
    getAll: () => api.get('/settings/'),
    update: (key: string, value: string) => api.put(`/settings/${key}`, { value }),
    getQuota: () => api.get('/settings/quota/current'),
    getRisk: () => api.get('/settings/risk/assessment'),
}

// Gamification
export const gamificationApi = {
    dashboard: () => api.get('/gamification/dashboard'),
    progress: () => api.get('/gamification/progress'),
    badges: () => api.get('/gamification/badges'),
    dailyGoal: () => api.get('/gamification/daily-goal'),
    dailySummary: () => api.get('/gamification/daily-summary'),
}

// Telegram Live (READ-ONLY MODE)
export const telegramApi = {
    // Init & Auth
    init: (apiId: number, apiHash: string) =>
        api.post('/telegram/init', { api_id: apiId, api_hash: apiHash }),
    startAuth: (phone: string) =>
        api.post('/telegram/auth/start', { phone }),
    verifyCode: (code: string) =>
        api.post('/telegram/auth/code', { code }),
    verify2fa: (password: string) =>
        api.post('/telegram/auth/2fa', { password }),
    getAuthStatus: () => api.get('/telegram/auth/status'),
    logout: () => api.post('/telegram/auth/logout'),

    // Dialogs & Messages (READ-ONLY)
    getDialogs: (limit?: number) =>
        api.get('/telegram/dialogs', { params: { limit } }),
    getMessages: (chatId: number, limit?: number, offsetId?: number) =>
        api.get(`/telegram/messages/${chatId}`, { params: { limit, offset_id: offsetId } }),
    getEntity: (identifier: string) =>
        api.get(`/telegram/entity/${identifier}`),

    // Import
    importFromChat: (chatId: number, limit?: number) =>
        api.post(`/telegram/import/${chatId}`, null, { params: { limit } }),

    // DISABLED: sendMessage - use Copy + paste in Telegram manually
}

// LLM
export const llmApi = {
    coach: (leadId: number) => api.post('/llm/coach', { lead_id: leadId }),
    objection: (leadId: number, objectionText: string) =>
        api.post('/llm/objection', { lead_id: leadId, objection_text: objectionText }),
}

export default api

