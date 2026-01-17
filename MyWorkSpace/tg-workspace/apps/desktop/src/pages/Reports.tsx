import { useEffect, useState } from 'react'
import {
    BarChart3, TrendingUp, MessageSquare, Target,
    Trophy, Calendar, ArrowUp, ArrowDown
} from 'lucide-react'
import { useStore } from '../store/useStore'
import { leadsApi, outreachApi, gamificationApi } from '../lib/api'
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    PieChart, Pie, Cell
} from 'recharts'

const COLORS = ['#0ea5e9', '#eab308', '#22c55e', '#a855f7', '#10b981', '#ef4444']

export default function Reports() {
    const { currentWorkspace } = useStore()
    const [loading, setLoading] = useState(true)
    const [leadStats, setLeadStats] = useState<any>(null)
    const [progress, setProgress] = useState<any>(null)
    const [todayStats, setTodayStats] = useState<any>(null)

    useEffect(() => {
        loadReports()
    }, [currentWorkspace])

    const loadReports = async () => {
        setLoading(true)
        try {
            const [progressRes, todayRes] = await Promise.all([
                gamificationApi.progress(),
                outreachApi.todayStats(),
            ])

            setProgress(progressRes.data)
            setTodayStats(todayRes.data)

            if (currentWorkspace) {
                const statsRes = await leadsApi.stats(currentWorkspace.id)
                setLeadStats(statsRes.data)
            }
        } catch (err) {
            console.error('Failed to load reports:', err)
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

    const funnelData = leadStats?.by_status ? [
        { name: 'Новые', value: leadStats.by_status.NEW || 0 },
        { name: 'Написали', value: leadStats.by_status.CONTACTED || 0 },
        { name: 'Ответили', value: leadStats.by_status.REPLIED || 0 },
        { name: 'Созвон', value: leadStats.by_status.CALL_SCHEDULED || 0 },
        { name: 'Выиграно', value: leadStats.by_status.WON || 0 },
        { name: 'Проиграно', value: leadStats.by_status.LOST || 0 },
    ] : []

    const categoryData = leadStats?.by_category ?
        Object.entries(leadStats.by_category).map(([name, value]) => ({
            name: name.replace(/_/g, ' ').substring(0, 15),
            value: value as number,
        })) : []

    const replyRate = todayStats?.risk_assessment?.stats?.reply_rate || 0

    return (
        <div className="space-y-6 animate-fadeIn">
            {/* Header */}
            <div>
                <h1 className="text-3xl font-bold text-white flex items-center gap-3">
                    📊 Отчеты
                </h1>
                <p className="text-white/70 mt-1">
                    Аналитика по лидам и конверсиям
                </p>
            </div>

            {/* Stats Overview */}
            <div className="grid grid-cols-4 gap-6">
                <StatCard
                    icon={<MessageSquare className="w-6 h-6" />}
                    label="Всего отправлено"
                    value={progress?.total_outreach || 0}
                    trend={null}
                    color="blue"
                />
                <StatCard
                    icon={<Target className="w-6 h-6" />}
                    label="Получено ответов"
                    value={progress?.total_replies || 0}
                    trend={null}
                    color="green"
                />
                <StatCard
                    icon={<Trophy className="w-6 h-6" />}
                    label="Выиграно сделок"
                    value={progress?.total_won || 0}
                    trend={null}
                    color="yellow"
                />
                <StatCard
                    icon={<TrendingUp className="w-6 h-6" />}
                    label="Общая выручка"
                    value={`${(progress?.total_revenue || 0).toLocaleString('ru-RU')} ₽`}
                    trend={null}
                    color="purple"
                />
            </div>

            <div className="grid grid-cols-2 gap-6">
                {/* Funnel Chart */}
                <div className="card">
                    <h2 className="text-lg font-bold text-gray-800 mb-4">📈 Воронка продаж</h2>
                    {funnelData.length > 0 ? (
                        <ResponsiveContainer width="100%" height={300}>
                            <BarChart data={funnelData} layout="vertical">
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis type="number" />
                                <YAxis type="category" dataKey="name" width={80} />
                                <Tooltip />
                                <Bar dataKey="value" fill="#0ea5e9" radius={[0, 4, 4, 0]}>
                                    {funnelData.map((_, index) => (
                                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                    ))}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    ) : (
                        <div className="h-[300px] flex items-center justify-center text-gray-400">
                            Нет данных
                        </div>
                    )}
                </div>

                {/* Category Distribution */}
                <div className="card">
                    <h2 className="text-lg font-bold text-gray-800 mb-4">🎯 По категориям</h2>
                    {categoryData.length > 0 ? (
                        <ResponsiveContainer width="100%" height={300}>
                            <PieChart>
                                <Pie
                                    data={categoryData}
                                    dataKey="value"
                                    nameKey="name"
                                    cx="50%"
                                    cy="50%"
                                    outerRadius={100}
                                    label={({ name, value }) => `${name}: ${value}`}
                                >
                                    {categoryData.map((_, index) => (
                                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                    ))}
                                </Pie>
                                <Tooltip />
                            </PieChart>
                        </ResponsiveContainer>
                    ) : (
                        <div className="h-[300px] flex items-center justify-center text-gray-400">
                            Нет данных
                        </div>
                    )}
                </div>
            </div>

            {/* Conversion Metrics */}
            <div className="card">
                <h2 className="text-lg font-bold text-gray-800 mb-4">📉 Показатели конверсии</h2>
                <div className="grid grid-cols-3 gap-6">
                    <MetricCard
                        label="Процент ответов"
                        value={`${replyRate}%`}
                        description="Отношение ответов к отправленным"
                        status={replyRate >= 10 ? 'good' : replyRate >= 5 ? 'medium' : 'bad'}
                    />
                    <MetricCard
                        label="Конверсия в созвон"
                        value={`${calculateConversion(
                            leadStats?.by_status?.CALL_SCHEDULED || 0,
                            leadStats?.by_status?.REPLIED || 0
                        )}%`}
                        description="От ответивших до созвона"
                        status="neutral"
                    />
                    <MetricCard
                        label="Конверсия в сделку"
                        value={`${calculateConversion(
                            leadStats?.by_status?.WON || 0,
                            leadStats?.by_status?.CONTACTED || 0
                        )}%`}
                        description="От написанных до выигранных"
                        status="neutral"
                    />
                </div>
            </div>

            {/* Risk Assessment */}
            {todayStats?.risk_assessment && (
                <div className={`card ${todayStats.risk_assessment.risk_level === 'HIGH' ? 'border-2 border-red-300' :
                        todayStats.risk_assessment.risk_level === 'MEDIUM' ? 'border-2 border-yellow-300' : ''
                    }`}>
                    <h2 className="text-lg font-bold text-gray-800 mb-4">⚠️ Оценка рисков</h2>
                    <div className="flex items-center gap-4 mb-4">
                        <div className={`text-3xl font-bold ${todayStats.risk_assessment.risk_level === 'HIGH' ? 'text-red-500' :
                                todayStats.risk_assessment.risk_level === 'MEDIUM' ? 'text-yellow-500' :
                                    'text-green-500'
                            }`}>
                            {todayStats.risk_assessment.risk_level}
                        </div>
                        <div className="text-gray-600">
                            Риск-скор: {todayStats.risk_assessment.risk_score}/100
                        </div>
                    </div>
                    <p className="text-gray-700">{todayStats.risk_assessment.recommendation}</p>
                    {todayStats.risk_assessment.warnings?.length > 0 && (
                        <ul className="mt-3 space-y-1">
                            {todayStats.risk_assessment.warnings.map((w: string, i: number) => (
                                <li key={i} className="text-yellow-700 text-sm">• {w}</li>
                            ))}
                        </ul>
                    )}
                </div>
            )}
        </div>
    )
}

function calculateConversion(numerator: number, denominator: number): number {
    if (denominator === 0) return 0
    return Math.round((numerator / denominator) * 100)
}

function StatCard({ icon, label, value, trend, color }: {
    icon: React.ReactNode
    label: string
    value: string | number
    trend: number | null
    color: string
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
            <div className="flex items-center justify-between">
                <span className="text-gray-500 text-sm">{label}</span>
                {trend !== null && (
                    <span className={`flex items-center text-sm ${trend >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                        {trend >= 0 ? <ArrowUp className="w-4 h-4" /> : <ArrowDown className="w-4 h-4" />}
                        {Math.abs(trend)}%
                    </span>
                )}
            </div>
        </div>
    )
}

function MetricCard({ label, value, description, status }: {
    label: string
    value: string
    description: string
    status: 'good' | 'medium' | 'bad' | 'neutral'
}) {
    const statusColors = {
        good: 'text-green-500',
        medium: 'text-yellow-500',
        bad: 'text-red-500',
        neutral: 'text-gray-700',
    }

    return (
        <div className="p-4 bg-gray-50 rounded-xl">
            <div className="text-sm text-gray-500 mb-1">{label}</div>
            <div className={`text-3xl font-bold ${statusColors[status]}`}>{value}</div>
            <div className="text-xs text-gray-400 mt-1">{description}</div>
        </div>
    )
}
