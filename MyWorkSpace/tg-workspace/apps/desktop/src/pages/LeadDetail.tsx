import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
    ArrowLeft, Copy, ExternalLink, Check, X, MessageSquare,
    Zap, Clock, Ban, Star, Send, RefreshCw, Sparkles, Shield, Info
} from 'lucide-react'
import { useStore } from '../store/useStore'
import { leadsApi, outreachApi, llmApi } from '../lib/api'

const STATUS_OPTIONS = [
    { value: 'NEW', label: '🆕 Новый', color: 'bg-blue-500' },
    { value: 'CONTACTED', label: '📤 Написали', color: 'bg-yellow-500' },
    { value: 'REPLIED', label: '💬 Ответил', color: 'bg-green-500' },
    { value: 'CALL_SCHEDULED', label: '📞 Созвон', color: 'bg-purple-500' },
    { value: 'WON', label: '✅ Выиграно', color: 'bg-emerald-500' },
    { value: 'LOST', label: '❌ Проиграно', color: 'bg-red-500' },
]

export default function LeadDetail() {
    const { leadId } = useParams()
    const navigate = useNavigate()
    const { addNotification } = useStore()

    const [lead, setLead] = useState<any>(null)
    const [loading, setLoading] = useState(true)
    const [outreachHistory, setOutreachHistory] = useState<any[]>([])
    const [notes, setNotes] = useState<any[]>([])

    const [draftMessage, setDraftMessage] = useState('')
    const [generating, setGenerating] = useState(false)
    const [canContact, setCanContact] = useState<any>(null)
    const [coachAdvice, setCoachAdvice] = useState<any>(null)
    const [copied, setCopied] = useState(false)

    useEffect(() => {
        if (leadId) {
            loadLeadData()
        }
    }, [leadId])

    const loadLeadData = async () => {
        setLoading(true)
        try {
            const [leadRes, historyRes, notesRes, canContactRes] = await Promise.all([
                leadsApi.get(parseInt(leadId!)),
                outreachApi.history(parseInt(leadId!)),
                leadsApi.getNotes(parseInt(leadId!)),
                leadsApi.canContact(parseInt(leadId!)),
            ])

            setLead(leadRes.data)
            setOutreachHistory(historyRes.data)
            setNotes(notesRes.data)
            setCanContact(canContactRes.data)
        } catch (err) {
            console.error('Failed to load lead:', err)
            addNotification('error', 'Не удалось загрузить данные лида')
        } finally {
            setLoading(false)
        }
    }

    const generateMessage = async () => {
        setGenerating(true)
        try {
            const res = await outreachApi.generate({ lead_id: parseInt(leadId!) })
            setDraftMessage(res.data.generated_message)
            addNotification('success', 'Сообщение сгенерировано')
        } catch (err) {
            console.error('Failed to generate:', err)
            addNotification('error', 'Ошибка генерации сообщения')
        } finally {
            setGenerating(false)
        }
    }

    const getCoachAdvice = async () => {
        try {
            const res = await llmApi.coach(parseInt(leadId!))
            setCoachAdvice(res.data)
        } catch (err) {
            console.error('Failed to get advice:', err)
        }
    }

    const copyMessage = () => {
        navigator.clipboard.writeText(draftMessage)
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
        addNotification('success', 'Скопировано!')
    }

    const openTelegram = () => {
        const author = lead?.message_author
        if (author && author.startsWith('@')) {
            window.open(`https://t.me/${author.slice(1)}`, '_blank')
        } else {
            window.open('https://t.me/', '_blank')
        }
    }

    const markAsSent = async () => {
        try {
            // First create draft if not exists
            const draftRes = await outreachApi.createDraft({
                lead_id: parseInt(leadId!),
                message_text: draftMessage,
            })

            // Then mark as sent
            const sentRes = await outreachApi.markSent(draftRes.data.id)

            addNotification('success', `Отправлено! +${sentRes.data.xp_earned} XP`)

            // Reload data
            loadLeadData()
            setDraftMessage('')
        } catch (err: any) {
            addNotification('error', err.response?.data?.detail || 'Ошибка')
        }
    }

    const updateStatus = async (newStatus: string) => {
        try {
            const res = await leadsApi.updateStatus(parseInt(leadId!), { status: newStatus })
            setLead({ ...lead, status: newStatus })
            addNotification('success', 'Статус обновлен')

            if (res.data.new_badges?.length > 0) {
                res.data.new_badges.forEach((badge: any) => {
                    addNotification('success', `🏆 Новый бейдж: ${badge.icon} ${badge.name}`)
                })
            }
        } catch (err) {
            addNotification('error', 'Ошибка обновления статуса')
        }
    }

    const toggleDnc = async () => {
        try {
            await leadsApi.updateDnc(parseInt(leadId!), {
                do_not_contact: !lead.do_not_contact,
                reason: 'Ручное добавление',
            })
            setLead({ ...lead, do_not_contact: !lead.do_not_contact })
            addNotification('success', lead.do_not_contact ? 'Убран из DNC' : 'Добавлен в DNC')
        } catch (err) {
            addNotification('error', 'Ошибка')
        }
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="animate-spin rounded-full h-12 w-12 border-4 border-white border-t-transparent"></div>
            </div>
        )
    }

    if (!lead) {
        return (
            <div className="card text-center py-12">
                <h2 className="text-xl font-bold text-gray-800">Лид не найден</h2>
            </div>
        )
    }

    return (
        <div className="space-y-6 animate-fadeIn">
            {/* Header */}
            <div className="flex items-center gap-4">
                <button
                    onClick={() => navigate('/leads')}
                    className="glass rounded-full p-2 hover:bg-white/30 transition-colors"
                >
                    <ArrowLeft className="w-6 h-6 text-white" />
                </button>
                <div className="flex-1">
                    <h1 className="text-2xl font-bold text-white">{lead.message_author || 'Лид'}</h1>
                    <p className="text-white/70">{lead.category}</p>
                </div>
                <button
                    onClick={toggleDnc}
                    className={`btn-secondary flex items-center gap-2 ${lead.do_not_contact ? 'bg-red-500/30' : ''}`}
                >
                    <Ban className="w-4 h-4" />
                    {lead.do_not_contact ? 'В DNC' : 'Добавить в DNC'}
                </button>
            </div>

            <div className="grid grid-cols-3 gap-6">
                {/* Left Column - Lead Info & Message */}
                <div className="col-span-2 space-y-6">
                    {/* Original Message */}
                    <div className="card">
                        <h2 className="text-lg font-bold text-gray-800 mb-4">📝 Исходное сообщение</h2>
                        <div className="bg-gray-50 rounded-xl p-4">
                            <p className="text-gray-700 whitespace-pre-wrap">{lead.message_text}</p>
                        </div>
                        <div className="flex items-center gap-4 mt-4 text-sm text-gray-500">
                            <span>Fit: {Math.round(lead.fit_score * 100)}%</span>
                            <span>Money: {Math.round(lead.money_score * 100)}%</span>
                            <span>Confidence: {Math.round(lead.confidence * 100)}%</span>
                        </div>
                    </div>

                    {/* Message Composer */}
                    <div className="card">
                        <div className="flex items-center justify-between mb-4">
                            <h2 className="text-lg font-bold text-gray-800">✍️ Написать сообщение</h2>
                            <button
                                onClick={generateMessage}
                                disabled={generating}
                                className="btn-primary flex items-center gap-2"
                            >
                                <Sparkles className={`w-4 h-4 ${generating ? 'animate-spin' : ''}`} />
                                {generating ? 'Генерация...' : 'Сгенерировать'}
                            </button>
                        </div>

                        {/* Safety Info */}
                        <div className="flex items-center gap-3 p-3 bg-green-50 border border-green-200 rounded-xl mb-4">
                            <Shield className="w-5 h-5 text-green-600 flex-shrink-0" />
                            <p className="text-sm text-green-700">
                                <strong>Безопасный режим:</strong> Сообщения не отправляются автоматически.
                                Скопируйте текст и вставьте в Telegram вручную.
                            </p>
                        </div>

                        {/* Can Contact Check */}
                        {canContact && !canContact.can_contact && (
                            <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-4">
                                <p className="text-red-700">{canContact.reason}</p>
                            </div>
                        )}

                        <textarea
                            value={draftMessage}
                            onChange={(e) => setDraftMessage(e.target.value)}
                            placeholder="Напишите или сгенерируйте сообщение..."
                            className="w-full h-32 px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-500 resize-none"
                        />

                        <div className="flex items-center gap-3 mt-4">
                            <button
                                onClick={copyMessage}
                                disabled={!draftMessage}
                                className="btn-ghost flex items-center gap-2"
                            >
                                {copied ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
                                {copied ? 'Скопировано!' : 'Копировать'}
                            </button>
                            <button
                                onClick={openTelegram}
                                className="btn-ghost flex items-center gap-2"
                            >
                                <ExternalLink className="w-4 h-4" />
                                Открыть Telegram
                            </button>
                            <div className="flex-1" />
                            <button
                                onClick={markAsSent}
                                disabled={!draftMessage || !canContact?.can_contact}
                                className="btn-primary flex items-center gap-2"
                            >
                                <Send className="w-4 h-4" />
                                Я отправил
                            </button>
                        </div>

                        {/* Quota Info */}
                        {canContact?.quota && (
                            <div className="mt-4 p-3 bg-gray-50 rounded-lg text-sm text-gray-600">
                                📊 Отправлено сегодня: {canContact.quota.sent_today} / {canContact.quota.daily_limit}
                                {canContact.quota.warning && (
                                    <span className="ml-2 text-orange-600">{canContact.quota.warning}</span>
                                )}
                            </div>
                        )}
                    </div>

                    {/* Outreach History */}
                    {outreachHistory.length > 0 && (
                        <div className="card">
                            <h2 className="text-lg font-bold text-gray-800 mb-4">📨 История сообщений</h2>
                            <div className="space-y-4">
                                {outreachHistory.map((msg) => (
                                    <div key={msg.id} className="bg-gray-50 rounded-xl p-4">
                                        <div className="flex items-center justify-between mb-2">
                                            <span className="text-sm text-gray-500">
                                                {new Date(msg.created_at).toLocaleString('ru-RU')}
                                            </span>
                                            <span className={`badge ${msg.sent_at ? 'badge-success' : 'badge-warning'}`}>
                                                {msg.sent_at ? '✓ Отправлено' : '📝 Черновик'}
                                            </span>
                                        </div>
                                        <p className="text-gray-700">{msg.message_text}</p>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>

                {/* Right Column - Status & Actions */}
                <div className="space-y-6">
                    {/* Status */}
                    <div className="card">
                        <h2 className="text-lg font-bold text-gray-800 mb-4">📋 Статус</h2>
                        <div className="space-y-2">
                            {STATUS_OPTIONS.map((option) => (
                                <button
                                    key={option.value}
                                    onClick={() => updateStatus(option.value)}
                                    className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${lead.status === option.value
                                        ? `${option.color} text-white`
                                        : 'bg-gray-50 hover:bg-gray-100 text-gray-700'
                                        }`}
                                >
                                    <div className={`w-3 h-3 rounded-full ${option.color}`} />
                                    {option.label}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* AI Coach */}
                    <div className="card">
                        <div className="flex items-center justify-between mb-4">
                            <h2 className="text-lg font-bold text-gray-800">🤖 AI Coach</h2>
                            <button onClick={getCoachAdvice} className="btn-ghost">
                                <RefreshCw className="w-4 h-4" />
                            </button>
                        </div>

                        {coachAdvice ? (
                            <div className="space-y-3">
                                <div className="p-3 bg-primary-50 rounded-lg">
                                    <div className="text-sm font-medium text-primary-800 mb-1">Следующий шаг</div>
                                    <p className="text-primary-700">{coachAdvice.next_action}</p>
                                </div>
                                {coachAdvice.one_liner_tip && (
                                    <div className="p-3 bg-yellow-50 rounded-lg">
                                        <p className="text-yellow-800">💡 {coachAdvice.one_liner_tip}</p>
                                    </div>
                                )}
                                {coachAdvice.success_probability && (
                                    <div className="text-sm text-gray-500">
                                        Вероятность успеха: {Math.round(coachAdvice.success_probability * 100)}%
                                    </div>
                                )}
                            </div>
                        ) : (
                            <p className="text-gray-500 text-sm">
                                Нажмите кнопку для получения рекомендаций
                            </p>
                        )}
                    </div>

                    {/* Score Breakdown */}
                    <div className="card">
                        <h2 className="text-lg font-bold text-gray-800 mb-4">⭐ Скоринг</h2>
                        <div className="space-y-3">
                            <ScoreRow label="Общий скор" value={lead.total_score} />
                            <ScoreRow label="Fit score" value={lead.fit_score} />
                            <ScoreRow label="Money score" value={lead.money_score} />
                            <ScoreRow label="Recency" value={lead.recency_score} />
                            <ScoreRow label="Confidence" value={lead.confidence} />
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}

function ScoreRow({ label, value }: { label: string; value: number }) {
    const percent = Math.round(value * 100)
    const color = percent >= 70 ? 'bg-green-500' : percent >= 40 ? 'bg-yellow-500' : 'bg-gray-300'

    return (
        <div>
            <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600">{label}</span>
                <span className="font-medium">{percent}%</span>
            </div>
            <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                <div className={`h-full ${color} rounded-full`} style={{ width: `${percent}%` }} />
            </div>
        </div>
    )
}
