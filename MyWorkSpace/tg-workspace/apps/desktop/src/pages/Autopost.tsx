import { useState, useEffect } from 'react'
import {
    Clock, Plus, Trash2, Play, Square, RefreshCw, Check,
    MessageSquare, Settings, Loader, AlertTriangle
} from 'lucide-react'
import { telegramApi } from '../lib/api'
import { useStore } from '../store/useStore'
import api from '../lib/api'

interface AutopostConfig {
    enabled: boolean
    message_text: string
    chat_ids: number[]
    chat_names: Record<number, string>
    schedule_time: string
    interval_seconds: number
    randomize_order: boolean
    text_variations: string[]
    last_run: string | null
    next_run: string | null
    ai_rewrite: boolean
}

interface Dialog {
    id: number
    name: string
    type: string
}

export default function Autopost() {
    const { addNotification } = useStore()

    const [config, setConfig] = useState<AutopostConfig | null>(null)
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)
    const [running, setRunning] = useState(false)
    const [runStatus, setRunStatus] = useState<any>(null)

    // Form state
    const [messageText, setMessageText] = useState('')
    const [scheduleTime, setScheduleTime] = useState('10:00')
    const [intervalSeconds, setIntervalSeconds] = useState(60)
    const [randomizeOrder, setRandomizeOrder] = useState(true)
    const [aiRewrite, setAiRewrite] = useState(false)

    // Chat selection
    const [dialogs, setDialogs] = useState<Dialog[]>([])
    const [showChatSelector, setShowChatSelector] = useState(false)
    const [loadingDialogs, setLoadingDialogs] = useState(false)

    useEffect(() => {
        loadConfig()
    }, [])

    useEffect(() => {
        if (running) {
            const interval = setInterval(loadRunStatus, 2000)
            return () => clearInterval(interval)
        }
    }, [running])

    const loadConfig = async () => {
        try {
            const res = await api.get('/autopost/config')
            setConfig(res.data)
            setMessageText(res.data.message_text || '')
            setScheduleTime(res.data.schedule_time || '10:00')
            setIntervalSeconds(res.data.interval_seconds || 60)
            setRandomizeOrder(res.data.randomize_order ?? true)
            setAiRewrite(res.data.ai_rewrite ?? false)
        } catch (err) {
            console.error('Failed to load config:', err)
        } finally {
            setLoading(false)
        }
    }

    const loadDialogs = async () => {
        setLoadingDialogs(true)
        try {
            const res = await telegramApi.getDialogs(100)
            setDialogs(res.data.dialogs || [])
            setShowChatSelector(true)
        } catch (err: any) {
            if (err.response?.status === 401) {
                addNotification('error', 'Telegram не подключен. Подключитесь в настройках.')
            } else {
                addNotification('error', 'Ошибка загрузки чатов')
            }
        } finally {
            setLoadingDialogs(false)
        }
    }

    const loadRunStatus = async () => {
        try {
            const res = await api.get('/autopost/status')
            setRunStatus(res.data)
            if (!res.data.is_running && running) {
                setRunning(false)
                addNotification('success', 'Автопостинг завершен')
                loadConfig()
            }
        } catch (err) {
            console.error('Failed to load status:', err)
        }
    }

    const saveConfig = async () => {
        setSaving(true)
        try {
            await api.put('/autopost/config', {
                message_text: messageText,
                schedule_time: scheduleTime,
                interval_seconds: intervalSeconds,
                randomize_order: randomizeOrder,
                ai_rewrite: aiRewrite
            })
            addNotification('success', 'Настройки сохранены')
            loadConfig()
        } catch (err) {
            addNotification('error', 'Ошибка сохранения')
        } finally {
            setSaving(false)
        }
    }

    const addChat = async (dialog: Dialog) => {
        try {
            await api.post('/autopost/chats/add', {
                chat_id: dialog.id,
                chat_name: dialog.name
            })
            loadConfig()
            addNotification('success', `Добавлен: ${dialog.name}`)
        } catch (err) {
            addNotification('error', 'Ошибка добавления')
        }
    }

    const removeChat = async (chatId: number) => {
        try {
            await api.post('/autopost/chats/remove', { chat_id: chatId })
            loadConfig()
        } catch (err) {
            addNotification('error', 'Ошибка удаления')
        }
    }

    const runAutopost = async () => {
        if (!config?.chat_ids.length) {
            addNotification('error', 'Добавьте чаты для постинга')
            return
        }
        if (!messageText.trim()) {
            addNotification('error', 'Введите текст сообщения')
            return
        }

        // Save config first
        await saveConfig()

        try {
            await api.post('/autopost/run')
            setRunning(true)
            addNotification('success', 'Автопостинг запущен!')
        } catch (err: any) {
            addNotification('error', err.response?.data?.detail || 'Ошибка запуска')
        }
    }

    const stopAutopost = async () => {
        try {
            await api.post('/autopost/stop')
            setRunning(false)
            addNotification('info', 'Автопостинг остановлен')
        } catch (err) {
            addNotification('error', 'Ошибка остановки')
        }
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <Loader className="w-8 h-8 animate-spin text-white" />
            </div>
        )
    }

    const totalTime = (config?.chat_ids.length || 0) * intervalSeconds
    const totalMinutes = Math.ceil(totalTime / 60)

    return (
        <div className="space-y-6 animate-fadeIn">
            {/* Header */}
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold text-white flex items-center gap-3">
                        📢 Автопостинг
                    </h1>
                    <p className="text-white/70 mt-1">
                        Публикация сообщений в фриланс-чаты
                    </p>
                </div>
                <div className="flex gap-3">
                    {running ? (
                        <button onClick={stopAutopost} className="btn-secondary flex items-center gap-2">
                            <Square className="w-5 h-5" />
                            Остановить
                        </button>
                    ) : (
                        <button onClick={runAutopost} className="btn-primary flex items-center gap-2">
                            <Play className="w-5 h-5" />
                            Запустить сейчас
                        </button>
                    )}
                </div>
            </div>

            {/* Running Status */}
            {running && runStatus && (
                <div className="glass rounded-xl p-4">
                    <div className="flex items-center gap-3 mb-3">
                        <Loader className="w-5 h-5 animate-spin text-white" />
                        <span className="text-white font-medium">Идёт постинг...</span>
                        <span className="text-white/60">
                            {runStatus.log?.length || 0} / {config?.chat_ids.length || 0}
                        </span>
                    </div>
                    <div className="space-y-2 max-h-40 overflow-auto">
                        {runStatus.log?.map((entry: any, i: number) => (
                            <div key={i} className="flex items-center gap-2 text-sm text-white/80">
                                {entry.status === 'success' ? (
                                    <Check className="w-4 h-4 text-green-400" />
                                ) : entry.status === 'error' ? (
                                    <AlertTriangle className="w-4 h-4 text-red-400" />
                                ) : (
                                    <Loader className="w-4 h-4 animate-spin" />
                                )}
                                <span>{entry.chat_name}</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            <div className="grid grid-cols-2 gap-6">
                {/* Message Editor */}
                <div className="card">
                    <h2 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
                        <MessageSquare className="w-5 h-5" />
                        Текст сообщения
                    </h2>
                    <textarea
                        value={messageText}
                        onChange={(e) => setMessageText(e.target.value)}
                        placeholder="Введите текст для публикации...

Пример:
🔥 Разработка Telegram ботов, автоматизация, интеграции

✅ Парсеры и скраперы
✅ Интеграция с CRM
✅ Автоматизация бизнес-процессов

📩 @username"
                        className="w-full h-48 px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-500 resize-none"
                    />
                    <div className="mt-4 flex items-center justify-between">
                        <span className="text-sm text-gray-500">
                            {messageText.length} символов
                        </span>
                        <button
                            onClick={saveConfig}
                            disabled={saving}
                            className="btn-primary flex items-center gap-2"
                        >
                            {saving ? <Loader className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                            Сохранить
                        </button>
                    </div>
                </div>

                {/* Settings */}
                <div className="card">
                    <h2 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
                        <Settings className="w-5 h-5" />
                        Настройки
                    </h2>

                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                Время запуска (ежедневно)
                            </label>
                            <input
                                type="time"
                                value={scheduleTime}
                                onChange={(e) => setScheduleTime(e.target.value)}
                                className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-500"
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                Интервал между чатами (секунды)
                            </label>
                            <input
                                type="number"
                                min={30}
                                max={300}
                                value={intervalSeconds}
                                onChange={(e) => setIntervalSeconds(parseInt(e.target.value) || 60)}
                                className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-500"
                            />
                            <p className="text-xs text-gray-500 mt-1">Минимум 30 секунд для безопасности</p>
                        </div>

                        <div className="flex items-center gap-3">
                            <input
                                type="checkbox"
                                id="randomize"
                                checked={randomizeOrder}
                                onChange={(e) => setRandomizeOrder(e.target.checked)}
                                className="w-5 h-5 rounded"
                            />
                            <label htmlFor="randomize" className="text-gray-700">
                                Случайный порядок чатов
                            </label>
                        </div>

                        <div className="flex items-center gap-3 bg-purple-50 p-3 rounded-xl border border-purple-100">
                            <input
                                type="checkbox"
                                id="ai_rewrite"
                                checked={aiRewrite}
                                onChange={(e) => setAiRewrite(e.target.checked)}
                                className="w-5 h-5 rounded text-purple-600 focus:ring-purple-500"
                            />
                            <div>
                                <label htmlFor="ai_rewrite" className="text-gray-800 font-medium flex items-center gap-2">
                                    ✨ AI Рерайт текста (Silver Bullet)
                                </label>
                                <p className="text-xs text-gray-500">
                                    Каждое сообщение будет уникальным. Защита от спам-фильтров 99%.
                                </p>
                            </div>
                        </div>

                        {config?.chat_ids.length ? (
                            <div className="p-3 bg-blue-50 rounded-lg text-sm text-blue-700">
                                ⏱️ Примерное время: <strong>{totalMinutes} мин</strong> для {config.chat_ids.length} чатов
                            </div>
                        ) : null}

                        {config?.last_run && (
                            <div className="text-sm text-gray-500">
                                Последний запуск: {new Date(config.last_run).toLocaleString('ru-RU')}
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Chat List */}
            <div className="card">
                <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
                        📋 Чаты для постинга ({config?.chat_ids.length || 0})
                    </h2>
                    <button
                        onClick={loadDialogs}
                        disabled={loadingDialogs}
                        className="btn-primary flex items-center gap-2"
                    >
                        {loadingDialogs ? <Loader className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                        Добавить чаты
                    </button>
                </div>

                {config?.chat_ids.length === 0 ? (
                    <div className="text-center py-8 text-gray-400">
                        <MessageSquare className="w-12 h-12 mx-auto mb-2 opacity-50" />
                        <p>Нет чатов</p>
                        <p className="text-sm">Нажмите "Добавить чаты" чтобы выбрать группы</p>
                    </div>
                ) : (
                    <div className="grid grid-cols-2 gap-3">
                        {config?.chat_ids.map((chatId) => (
                            <div
                                key={chatId}
                                className="flex items-center justify-between p-3 bg-gray-50 rounded-xl"
                            >
                                <span className="font-medium text-gray-800">
                                    {config.chat_names[chatId] || chatId}
                                </span>
                                <button
                                    onClick={() => removeChat(chatId)}
                                    className="p-2 hover:bg-red-100 rounded-lg text-gray-400 hover:text-red-500"
                                >
                                    <Trash2 className="w-4 h-4" />
                                </button>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Chat Selector Modal */}
            {showChatSelector && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <div className="bg-white rounded-2xl p-6 w-[600px] max-h-[80vh] overflow-hidden flex flex-col animate-fadeIn">
                        <div className="flex items-center justify-between mb-4">
                            <h2 className="text-xl font-bold text-gray-800">Выберите чаты</h2>
                            <button
                                onClick={() => setShowChatSelector(false)}
                                className="p-2 hover:bg-gray-100 rounded-lg"
                            >
                                ✕
                            </button>
                        </div>
                        <p className="text-gray-500 text-sm mb-4">
                            Выберите группы/каналы для автопостинга. Только группы где вы можете писать.
                        </p>
                        <div className="flex-1 overflow-auto space-y-2">
                            {dialogs
                                .filter(d => d.type === 'group' || d.type === 'channel')
                                .map((dialog) => {
                                    const isAdded = config?.chat_ids.includes(dialog.id)
                                    return (
                                        <div
                                            key={dialog.id}
                                            className={`flex items-center justify-between p-3 rounded-xl cursor-pointer transition-all ${isAdded ? 'bg-green-100' : 'bg-gray-50 hover:bg-gray-100'
                                                }`}
                                            onClick={() => !isAdded && addChat(dialog)}
                                        >
                                            <div className="flex items-center gap-3">
                                                <span className="text-xl">
                                                    {dialog.type === 'channel' ? '📢' : '👥'}
                                                </span>
                                                <span className="font-medium text-gray-800">{dialog.name}</span>
                                            </div>
                                            {isAdded ? (
                                                <Check className="w-5 h-5 text-green-600" />
                                            ) : (
                                                <Plus className="w-5 h-5 text-gray-400" />
                                            )}
                                        </div>
                                    )
                                })}
                        </div>
                        <button
                            onClick={() => setShowChatSelector(false)}
                            className="mt-4 w-full btn-primary"
                        >
                            Готово
                        </button>
                    </div>
                </div>
            )}
        </div>
    )
}
