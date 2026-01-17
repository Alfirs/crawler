import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
    Search, Filter, SortAsc, RefreshCw, ExternalLink,
    Star, Clock, MessageSquare, Ban
} from 'lucide-react'
import { useStore } from '../store/useStore'
import { leadsApi } from '../lib/api'

interface Lead {
    id: number
    type: string
    category: string
    status: string
    total_score: number
    fit_score: number
    money_score: number
    message_text: string
    message_author: string
    message_date: string
    do_not_contact: boolean
    contact_count: number
    outreach_count: number
}

const STATUS_LABELS: Record<string, string> = {
    NEW: '🆕 Новый',
    CONTACTED: '📤 Написали',
    REPLIED: '💬 Ответил',
    CALL_SCHEDULED: '📞 Созвон',
    WON: '✅ Выиграно',
    LOST: '❌ Проиграно',
}

const STATUS_COLORS: Record<string, string> = {
    NEW: 'bg-blue-100 text-blue-800',
    CONTACTED: 'bg-yellow-100 text-yellow-800',
    REPLIED: 'bg-green-100 text-green-800',
    CALL_SCHEDULED: 'bg-purple-100 text-purple-800',
    WON: 'bg-emerald-100 text-emerald-800',
    LOST: 'bg-red-100 text-red-800',
}

const CATEGORY_LABELS: Record<string, string> = {
    Bots_TG_WA_VK: '🤖 Боты',
    Landing_Sites: '🌐 Сайты',
    Parsing_Analytics_Reports: '📊 Парсинг',
    Integrations_Sheets_CRM_n8n: '🔗 Интеграции',
    Sales_CRM_Process: '💼 CRM',
    Autoposting_ContentFactory: '📱 Автопостинг',
    Other: '📁 Другое',
}

export default function LeadsInbox() {
    const { currentWorkspace, addNotification } = useStore()
    const navigate = useNavigate()
    const [leads, setLeads] = useState<Lead[]>([])
    const [loading, setLoading] = useState(true)
    const [filters, setFilters] = useState({
        status: '',
        category: '',
        minScore: 0,
        sortBy: 'total_score',
        sortOrder: 'desc',
    })

    useEffect(() => {
        if (currentWorkspace) {
            loadLeads()
        }
    }, [currentWorkspace, filters])

    const loadLeads = async () => {
        if (!currentWorkspace) return

        setLoading(true)
        try {
            const res = await leadsApi.list(currentWorkspace.id, {
                status: filters.status || undefined,
                category: filters.category || undefined,
                min_score: filters.minScore > 0 ? filters.minScore : undefined,
                sort_by: filters.sortBy,
                sort_order: filters.sortOrder,
            })
            setLeads(res.data)
        } catch (err) {
            console.error('Failed to load leads:', err)
            addNotification('error', 'Не удалось загрузить лиды')
        } finally {
            setLoading(false)
        }
    }

    const getScoreColor = (score: number) => {
        if (score >= 0.7) return 'text-green-500'
        if (score >= 0.4) return 'text-yellow-500'
        return 'text-gray-400'
    }

    const formatDate = (dateStr: string) => {
        if (!dateStr) return ''
        const date = new Date(dateStr)
        return date.toLocaleDateString('ru-RU', { day: '2-digit', month: 'short' })
    }

    if (!currentWorkspace) {
        return (
            <div className="card text-center py-12">
                <h2 className="text-2xl font-bold text-gray-800 mb-4">📁 Выберите воркспейс</h2>
                <p className="text-gray-600 mb-6">
                    Для просмотра лидов необходимо выбрать или создать воркспейс
                </p>
                <button
                    onClick={() => navigate('/workspaces')}
                    className="btn-primary"
                >
                    Перейти к воркспейсам
                </button>
            </div>
        )
    }

    return (
        <div className="space-y-6 animate-fadeIn">
            {/* Header */}
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold text-white flex items-center gap-3">
                        🎯 Лиды
                    </h1>
                    <p className="text-white/70 mt-1">
                        {leads.length} лидов в {currentWorkspace.name}
                    </p>
                </div>
                <button
                    onClick={loadLeads}
                    className="btn-secondary flex items-center gap-2"
                >
                    <RefreshCw className="w-4 h-4" />
                    Обновить
                </button>
            </div>

            {/* Filters */}
            <div className="card">
                <div className="flex flex-wrap gap-4">
                    <select
                        value={filters.status}
                        onChange={(e) => setFilters({ ...filters, status: e.target.value })}
                        className="px-4 py-2 rounded-lg border border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-500"
                    >
                        <option value="">Все статусы</option>
                        {Object.entries(STATUS_LABELS).map(([value, label]) => (
                            <option key={value} value={value}>{label}</option>
                        ))}
                    </select>

                    <select
                        value={filters.category}
                        onChange={(e) => setFilters({ ...filters, category: e.target.value })}
                        className="px-4 py-2 rounded-lg border border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-500"
                    >
                        <option value="">Все категории</option>
                        {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
                            <option key={value} value={value}>{label}</option>
                        ))}
                    </select>

                    <div className="flex items-center gap-2">
                        <Star className="w-4 h-4 text-gray-400" />
                        <input
                            type="range"
                            min="0"
                            max="1"
                            step="0.1"
                            value={filters.minScore}
                            onChange={(e) => setFilters({ ...filters, minScore: parseFloat(e.target.value) })}
                            className="w-24"
                        />
                        <span className="text-sm text-gray-600">
                            {filters.minScore > 0 ? `≥ ${(filters.minScore * 100).toFixed(0)}%` : 'Любой скор'}
                        </span>
                    </div>

                    <select
                        value={`${filters.sortBy}_${filters.sortOrder}`}
                        onChange={(e) => {
                            const [sortBy, sortOrder] = e.target.value.split('_')
                            setFilters({ ...filters, sortBy, sortOrder })
                        }}
                        className="px-4 py-2 rounded-lg border border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-500"
                    >
                        <option value="total_score_desc">Лучший скор ↓</option>
                        <option value="total_score_asc">Худший скор ↑</option>
                        <option value="created_at_desc">Новые первыми</option>
                        <option value="created_at_asc">Старые первыми</option>
                    </select>
                </div>
            </div>

            {/* Leads List */}
            {loading ? (
                <div className="flex items-center justify-center h-64">
                    <div className="animate-spin rounded-full h-12 w-12 border-4 border-white border-t-transparent"></div>
                </div>
            ) : leads.length === 0 ? (
                <div className="card text-center py-12">
                    <Target className="w-16 h-16 mx-auto text-gray-300 mb-4" />
                    <h3 className="text-xl font-bold text-gray-700 mb-2">Нет лидов</h3>
                    <p className="text-gray-500">
                        Загрузите экспорт Telegram чата в воркспейсе для поиска лидов
                    </p>
                </div>
            ) : (
                <div className="space-y-4">
                    {leads.map((lead) => (
                        <div
                            key={lead.id}
                            onClick={() => navigate(`/leads/${lead.id}`)}
                            className="card cursor-pointer hover:shadow-xl"
                        >
                            <div className="flex items-start gap-4">
                                {/* Score */}
                                <div className="text-center">
                                    <div className={`text-3xl font-bold ${getScoreColor(lead.total_score)}`}>
                                        {Math.round(lead.total_score * 100)}
                                    </div>
                                    <div className="text-xs text-gray-400">скор</div>
                                </div>

                                {/* Content */}
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-3 mb-2">
                                        <span className={`badge ${STATUS_COLORS[lead.status] || 'bg-gray-100'}`}>
                                            {STATUS_LABELS[lead.status] || lead.status}
                                        </span>
                                        <span className="text-gray-400 text-sm">
                                            {CATEGORY_LABELS[lead.category] || lead.category}
                                        </span>
                                        {lead.do_not_contact && (
                                            <span className="badge badge-danger flex items-center gap-1">
                                                <Ban className="w-3 h-3" /> DNC
                                            </span>
                                        )}
                                    </div>

                                    <div className="flex items-center gap-2 mb-2">
                                        <span className="font-medium text-gray-800">
                                            {lead.message_author || 'Неизвестный автор'}
                                        </span>
                                        {lead.message_date && (
                                            <span className="text-gray-400 text-sm flex items-center gap-1">
                                                <Clock className="w-3 h-3" />
                                                {formatDate(lead.message_date)}
                                            </span>
                                        )}
                                    </div>

                                    <p className="text-gray-600 line-clamp-2">
                                        {lead.message_text}
                                    </p>

                                    <div className="flex items-center gap-4 mt-3 text-sm text-gray-400">
                                        <span className="flex items-center gap-1">
                                            <Star className={`w-4 h-4 ${getScoreColor(lead.fit_score)}`} />
                                            Fit: {Math.round(lead.fit_score * 100)}%
                                        </span>
                                        <span className="flex items-center gap-1">
                                            💰 Money: {Math.round(lead.money_score * 100)}%
                                        </span>
                                        {lead.outreach_count > 0 && (
                                            <span className="flex items-center gap-1">
                                                <MessageSquare className="w-4 h-4" />
                                                {lead.outreach_count} сообщений
                                            </span>
                                        )}
                                    </div>
                                </div>

                                {/* Arrow */}
                                <ExternalLink className="w-5 h-5 text-gray-300" />
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}
