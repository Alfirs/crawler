import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
    Target, MessageSquare, TrendingUp, Trophy, Flame, Star,
    ArrowRight, Clock, CheckCircle, Zap
} from 'lucide-react'
import { useStore } from '../store/useStore'
import { gamificationApi, outreachApi, leadsApi } from '../lib/api'

interface DashboardData {
    gamification: any
    todayStats: any
    leadStats: any
    pendingFollowups: any[]
}

export default function Dashboard() {
    const { currentWorkspace, addNotification } = useStore()
    const navigate = useNavigate()
    const [data, setData] = useState<DashboardData | null>(null)
    const [loading, setLoading] = useState(true)
    const [dailySummary, setDailySummary] = useState('')

    useEffect(() => {
        loadDashboardData()
    }, [currentWorkspace])

    const loadDashboardData = async () => {
        setLoading(true)
        try {
            const [gamification, todayStats] = await Promise.all([
                gamificationApi.dashboard(),
                outreachApi.todayStats(),
            ])

            let leadStats = null
            let pendingFollowups: any[] = []
            if (currentWorkspace) {
                const [stats, followups] = await Promise.all([
                    leadsApi.stats(currentWorkspace.id),
                    outreachApi.pendingFollowups(currentWorkspace.id),
                ])
                leadStats = stats.data
                pendingFollowups = followups.data
            }

            setData({
                gamification: gamification.data,
                todayStats: todayStats.data,
                leadStats,
                pendingFollowups,
            })

            // Load daily summary
            gamificationApi.dailySummary().then(res => {
                setDailySummary(res.data.summary)
            })
        } catch (err) {
            console.error('Failed to load dashboard:', err)
            addNotification('error', 'Не удалось загрузить данные')
        } finally {
            setLoading(false)
        }
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="animate-spin rounded-full h-12 w-12 border-4 border-white border-t-transparent"></div>
            </div>
        )
    }

    const g = data?.gamification
    const today = data?.todayStats
    const leads = data?.leadStats

    return (
        <div className="space-y-8 animate-fadeIn">
            {/* Header */}
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold text-white flex items-center gap-3">
                        🏠 Dashboard
                    </h1>
                    <p className="text-white/70 mt-1">
                        Добро пожаловать! Вот ваша сводка на сегодня.
                    </p>
                </div>
                {g?.streak?.current > 0 && (
                    <div className="glass rounded-2xl px-6 py-4 flex items-center gap-3">
                        <Flame className="w-8 h-8 text-orange-400 animate-pulse" />
                        <div>
                            <div className="text-white font-bold text-2xl">{g.streak.current}</div>
                            <div className="text-white/60 text-sm">дней подряд</div>
                        </div>
                    </div>
                )}
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-4 gap-6">
                <StatCard
                    icon={<MessageSquare className="w-6 h-6" />}
                    label="Отправлено сегодня"
                    value={today?.sent_today || 0}
                    subtext={`из ${today?.quota?.daily_limit || 15}`}
                    color="blue"
                    progress={(today?.sent_today / (today?.quota?.daily_limit || 15)) * 100}
                />
                <StatCard
                    icon={<Target className="w-6 h-6" />}
                    label="Ответов"
                    value={today?.replied_today || 0}
                    color="green"
                />
                <StatCard
                    icon={<Trophy className="w-6 h-6" />}
                    label="Уровень"
                    value={g?.level || 1}
                    subtext={`${g?.xp || 0} XP`}
                    color="yellow"
                />
                <StatCard
                    icon={<Star className="w-6 h-6" />}
                    label="Бейджей"
                    value={g?.badges_count || 0}
                    subtext={`из ${g?.total_badges || 13}`}
                    color="purple"
                />
            </div>

            {/* Daily Goals */}
            {g?.daily_goals && (
                <div className="card">
                    <h2 className="text-xl font-bold text-gray-800 mb-4 flex items-center gap-2">
                        🎯 Цели на сегодня
                    </h2>
                    <div className="grid grid-cols-3 gap-6">
                        <GoalProgress
                            label="Новые сообщения"
                            done={g.daily_goals.messages?.done || 0}
                            target={g.daily_goals.messages?.target || 20}
                            icon="📨"
                        />
                        <GoalProgress
                            label="Follow-up"
                            done={g.daily_goals.followups?.done || 0}
                            target={g.daily_goals.followups?.target || 5}
                            icon="🔄"
                        />
                        <GoalProgress
                            label="Движения воронки"
                            done={g.daily_goals.moves?.done || 0}
                            target={g.daily_goals.moves?.target || 1}
                            icon="📈"
                        />
                    </div>
                </div>
            )}

            <div className="grid grid-cols-2 gap-6">
                {/* Lead Funnel */}
                {leads && (
                    <div className="card">
                        <h2 className="text-xl font-bold text-gray-800 mb-4 flex items-center gap-2">
                            📊 Воронка лидов
                        </h2>
                        <div className="space-y-3">
                            <FunnelRow label="Новые" value={leads.by_status?.NEW || 0} color="bg-blue-500" />
                            <FunnelRow label="Написали" value={leads.by_status?.CONTACTED || 0} color="bg-yellow-500" />
                            <FunnelRow label="Ответили" value={leads.by_status?.REPLIED || 0} color="bg-green-500" />
                            <FunnelRow label="Созвон" value={leads.by_status?.CALL_SCHEDULED || 0} color="bg-purple-500" />
                            <FunnelRow label="Выиграно" value={leads.by_status?.WON || 0} color="bg-emerald-500" />
                            <FunnelRow label="Проиграно" value={leads.by_status?.LOST || 0} color="bg-red-500" />
                        </div>
                        <button
                            onClick={() => navigate('/leads')}
                            className="mt-4 text-primary-600 font-medium flex items-center gap-1 hover:gap-2 transition-all"
                        >
                            Открыть все лиды <ArrowRight className="w-4 h-4" />
                        </button>
                    </div>
                )}

                {/* Pending Follow-ups */}
                <div className="card">
                    <h2 className="text-xl font-bold text-gray-800 mb-4 flex items-center gap-2">
                        ⏰ Нужно написать
                    </h2>
                    {data?.pendingFollowups && data.pendingFollowups.length > 0 ? (
                        <div className="space-y-3">
                            {data.pendingFollowups.slice(0, 5).map((task) => (
                                <div
                                    key={task.task_id}
                                    className={`flex items-center justify-between p-3 rounded-xl ${task.is_overdue ? 'bg-red-50' : 'bg-gray-50'
                                        }`}
                                >
                                    <div className="flex items-center gap-3">
                                        <Clock className={`w-5 h-5 ${task.is_overdue ? 'text-red-500' : 'text-gray-400'}`} />
                                        <div>
                                            <div className="font-medium text-gray-800">{task.lead_author || 'Без имени'}</div>
                                            <div className="text-sm text-gray-500">{task.task_title || 'Follow-up'}</div>
                                        </div>
                                    </div>
                                    <button
                                        onClick={() => navigate(`/leads/${task.lead_id}`)}
                                        className="btn-ghost text-sm"
                                    >
                                        Открыть
                                    </button>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="text-center py-8 text-gray-400">
                            <CheckCircle className="w-12 h-12 mx-auto mb-2 opacity-50" />
                            <p>Нет срочных follow-up</p>
                        </div>
                    )}
                </div>
            </div>

            {/* AI Summary */}
            {dailySummary && (
                <div className="glass rounded-2xl p-6">
                    <div className="flex items-start gap-4">
                        <div className="w-12 h-12 rounded-full bg-gradient-to-r from-primary-500 to-accent-500 flex items-center justify-center">
                            <Zap className="w-6 h-6 text-white" />
                        </div>
                        <div>
                            <h3 className="text-white font-bold mb-1">🤖 AI Coach</h3>
                            <p className="text-white/80">{dailySummary}</p>
                        </div>
                    </div>
                </div>
            )}

            {/* Risk Assessment */}
            {today?.risk_assessment && today.risk_assessment.risk_level !== 'LOW' && (
                <div className={`rounded-2xl p-6 ${today.risk_assessment.risk_level === 'HIGH' ? 'bg-red-500/20' : 'bg-yellow-500/20'
                    }`}>
                    <p className="text-white font-medium">
                        {today.risk_assessment.recommendation}
                    </p>
                </div>
            )}
        </div>
    )
}

function StatCard({ icon, label, value, subtext, color, progress }: {
    icon: React.ReactNode
    label: string
    value: number | string
    subtext?: string
    color: string
    progress?: number
}) {
    const colors = {
        blue: 'from-blue-500 to-blue-600',
        green: 'from-green-500 to-green-600',
        yellow: 'from-yellow-500 to-orange-500',
        purple: 'from-purple-500 to-pink-500',
    }

    return (
        <div className="card">
            <div className={`w-12 h-12 rounded-xl bg-gradient-to-r ${colors[color as keyof typeof colors]} flex items-center justify-center text-white mb-4`}>
                {icon}
            </div>
            <div className="text-3xl font-bold text-gray-800">{value}</div>
            <div className="text-gray-500 text-sm">{label}</div>
            {subtext && <div className="text-gray-400 text-xs mt-1">{subtext}</div>}
            {progress !== undefined && (
                <div className="mt-3 progress-bar">
                    <div className="progress-bar-fill" style={{ width: `${Math.min(100, progress)}%` }} />
                </div>
            )}
        </div>
    )
}

function GoalProgress({ label, done, target, icon }: {
    label: string
    done: number
    target: number
    icon: string
}) {
    const percent = target > 0 ? (done / target) * 100 : 0
    const isComplete = done >= target

    return (
        <div className={`p-4 rounded-xl ${isComplete ? 'bg-green-50' : 'bg-gray-50'}`}>
            <div className="flex items-center justify-between mb-2">
                <span className="text-2xl">{icon}</span>
                {isComplete && <CheckCircle className="w-5 h-5 text-green-500" />}
            </div>
            <div className="text-sm text-gray-600 mb-1">{label}</div>
            <div className="text-2xl font-bold text-gray-800">{done} / {target}</div>
            <div className="mt-2 progress-bar">
                <div
                    className={`progress-bar-fill ${isComplete ? 'bg-green-500' : ''}`}
                    style={{ width: `${Math.min(100, percent)}%` }}
                />
            </div>
        </div>
    )
}

function FunnelRow({ label, value, color }: { label: string; value: number; color: string }) {
    return (
        <div className="flex items-center gap-3">
            <div className={`w-3 h-3 rounded-full ${color}`} />
            <span className="text-gray-600 flex-1">{label}</span>
            <span className="font-bold text-gray-800">{value}</span>
        </div>
    )
}
