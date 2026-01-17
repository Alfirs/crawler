// Shared TypeScript types for TG Workspace

// Enums
export enum LeadStatus {
    NEW = 'NEW',
    CONTACTED = 'CONTACTED',
    REPLIED = 'REPLIED',
    CALL_SCHEDULED = 'CALL_SCHEDULED',
    WON = 'WON',
    LOST = 'LOST',
}

export enum LeadType {
    TASK = 'TASK',
    VACANCY = 'VACANCY',
    OFFER = 'OFFER',
    SPAM = 'SPAM',
    CHATTER = 'CHATTER',
}

export enum LeadCategory {
    BOTS_TG_WA_VK = 'Bots_TG_WA_VK',
    LANDING_SITES = 'Landing_Sites',
    PARSING_ANALYTICS = 'Parsing_Analytics_Reports',
    INTEGRATIONS = 'Integrations_Sheets_CRM_n8n',
    SALES_CRM = 'Sales_CRM_Process',
    AUTOPOSTING = 'Autoposting_ContentFactory',
    OTHER = 'Other',
}

export enum GoalMode {
    LITE = 'lite',
    NORMAL = 'normal',
    HARD = 'hard',
}

// Models
export interface Workspace {
    id: number
    name: string
    description?: string
    created_at: string
    sources_count: number
    leads_count: number
}

export interface Source {
    id: number
    workspace_id: number
    type: string
    title: string
    link?: string
    file_path?: string
    created_at: string
    parsed_at?: string
    message_count: number
}

export interface Message {
    id: number
    source_id: number
    msg_id?: string
    date?: string
    author?: string
    author_id?: string
    text?: string
    created_at: string
}

export interface Lead {
    id: number
    workspace_id: number
    message_id: number
    type: LeadType
    category: LeadCategory
    fit_score: number
    money_score: number
    recency_score: number
    confidence: number
    total_score: number
    status: LeadStatus
    do_not_contact: boolean
    dnc_reason?: string
    last_contacted_at?: string
    contact_count: number
    expected_revenue?: number
    lost_reason?: string
    created_at: string
    // Joined data
    message_text?: string
    message_author?: string
    message_date?: string
    outreach_count?: number
    notes_count?: number
}

export interface Outreach {
    id: number
    lead_id: number
    message_text: string
    template_id?: number
    created_at: string
    sent_at?: string
    result_status?: string
    replied_at?: string
}

export interface Template {
    id: number
    name: string
    category?: string
    text: string
    variables?: string[]
    is_active: boolean
    usage_count: number
    success_rate?: number
    created_at: string
}

export interface UserProgress {
    xp: number
    level: number
    streak_days: number
    longest_streak: number
    total_outreach: number
    total_replies: number
    total_won: number
    total_revenue: number
}

export interface Badge {
    id: number
    name: string
    description?: string
    icon?: string
    is_earned: boolean
    earned_at?: string
}

export interface DailyGoal {
    date: string
    messages_target: number
    messages_done: number
    followups_target: number
    followups_done: number
    moves_target: number
    moves_done: number
    is_completed: boolean
}

// API Responses
export interface QuotaResponse {
    sent_today: number
    daily_limit: number
    remaining: number
    usage_percent: number
    can_send: boolean
    warning?: string
}

export interface RiskAssessment {
    risk_score: number
    risk_level: 'LOW' | 'MEDIUM' | 'HIGH'
    warnings: string[]
    recommendation: string
    stats: {
        sent_this_week: number
        replied_this_week: number
        reply_rate: number
    }
}

export interface GeneratedMessage {
    message: string
    hook?: string
    next_step?: string
    personalization_points?: string[]
    model_used?: string
}

export interface CoachAdvice {
    next_action: string
    approach?: string
    timing?: string
    risks?: string[]
    success_probability?: number
    one_liner_tip?: string
}
