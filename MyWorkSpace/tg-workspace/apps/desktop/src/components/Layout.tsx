import { Outlet, NavLink, useLocation } from 'react-router-dom'
import {
    Home, Target, MessageSquare, FileText, BarChart3, Settings,
    Zap, Trophy, Flame
} from 'lucide-react'
import { useStore } from '../store/useStore'
import { useEffect, useState } from 'react'
import { gamificationApi } from '../lib/api'
import Notifications from './Notifications'

const navItems = [
    { path: '/', icon: Home, label: '🏠 Dashboard', emoji: '🏠' },
    { path: '/leads', icon: Target, label: '🎯 Лиды', emoji: '🎯' },
    { path: '/telegram', icon: MessageSquare, label: '💬 Telegram', emoji: '💬' },
    { path: '/autopost', icon: Zap, label: '📢 Автопостинг', emoji: '📢' },
    { path: '/templates', icon: FileText, label: '🧠 Шаблоны', emoji: '🧠' },
    { path: '/reports', icon: BarChart3, label: '📊 Отчеты', emoji: '📊' },
    { path: '/settings', icon: Settings, label: '⚙️ Настройки', emoji: '⚙️' },
]

export default function Layout() {
    const { currentWorkspace, gamificationData, setGamificationData } = useStore()
    const location = useLocation()
    const [streakFire, setStreakFire] = useState(false)

    useEffect(() => {
        // Load gamification data
        gamificationApi.dashboard().then(res => {
            setGamificationData(res.data)
            if (res.data.streak?.current > 0) {
                setStreakFire(true)
            }
        }).catch(console.error)
    }, [])

    return (
        <div className="min-h-screen flex">
            {/* Sidebar */}
            <aside className="w-72 glass-dark flex flex-col">
                {/* Logo */}
                <div className="p-6 border-b border-white/10">
                    <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                        <span className="text-3xl">📱</span>
                        TG Workspace
                    </h1>
                    {currentWorkspace && (
                        <p className="text-white/60 text-sm mt-2 truncate">
                            {currentWorkspace.name}
                        </p>
                    )}
                </div>

                {/* Gamification Stats */}
                {gamificationData && (
                    <div className="p-4 border-b border-white/10">
                        <div className="glass rounded-xl p-4">
                            <div className="flex items-center justify-between mb-3">
                                <div className="flex items-center gap-2">
                                    <Trophy className="w-5 h-5 text-yellow-400" />
                                    <span className="text-white font-medium">
                                        Уровень {gamificationData.level}
                                    </span>
                                </div>
                                {gamificationData.streak?.current > 0 && (
                                    <div className="flex items-center gap-1 text-orange-400">
                                        <Flame className={`w-5 h-5 ${streakFire ? 'animate-pulse' : ''}`} />
                                        <span className="font-bold">{gamificationData.streak.current}</span>
                                    </div>
                                )}
                            </div>

                            {/* XP Progress */}
                            <div className="mb-2">
                                <div className="flex justify-between text-xs text-white/60 mb-1">
                                    <span>XP</span>
                                    <span>{gamificationData.xp_progress?.current || 0} / {gamificationData.xp_progress?.needed || 100}</span>
                                </div>
                                <div className="progress-bar bg-white/20">
                                    <div
                                        className="progress-bar-fill"
                                        style={{ width: `${gamificationData.xp_progress?.percent || 0}%` }}
                                    />
                                </div>
                            </div>

                            {/* Daily Goal */}
                            <div>
                                <div className="flex justify-between text-xs text-white/60 mb-1">
                                    <span>📨 Сообщения сегодня</span>
                                    <span>
                                        {gamificationData.daily_goals?.messages?.done || 0} /
                                        {gamificationData.daily_goals?.messages?.target || 20}
                                    </span>
                                </div>
                                <div className="progress-bar bg-white/20">
                                    <div
                                        className="progress-bar-fill bg-gradient-to-r from-green-400 to-emerald-500"
                                        style={{ width: `${gamificationData.daily_goals?.messages?.percent || 0}%` }}
                                    />
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* Navigation */}
                <nav className="flex-1 p-4">
                    <ul className="space-y-2">
                        {navItems.map((item) => (
                            <li key={item.path}>
                                <NavLink
                                    to={item.path}
                                    className={({ isActive }) =>
                                        `flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 ${isActive
                                            ? 'bg-white/20 text-white shadow-lg'
                                            : 'text-white/70 hover:bg-white/10 hover:text-white'
                                        }`
                                    }
                                >
                                    <span className="text-xl">{item.emoji}</span>
                                    <span className="font-medium">{item.label.replace(item.emoji + ' ', '')}</span>
                                </NavLink>
                            </li>
                        ))}
                    </ul>
                </nav>

                {/* Workspace Selector */}
                <div className="p-4 border-t border-white/10">
                    <NavLink
                        to="/workspaces"
                        className="flex items-center gap-3 px-4 py-3 rounded-xl text-white/70 hover:bg-white/10 hover:text-white transition-all"
                    >
                        <span className="text-xl">📁</span>
                        <span className="font-medium">Воркспейсы</span>
                    </NavLink>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 overflow-auto">
                <div className="p-8">
                    <Outlet />
                </div>
            </main>

            {/* Notifications */}
            <Notifications />
        </div>
    )
}
