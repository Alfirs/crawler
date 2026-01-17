import { useEffect, useState } from 'react'
import { Save, AlertTriangle, Shield, Target, Key } from 'lucide-react'
import { useStore } from '../store/useStore'
import { settingsApi } from '../lib/api'
import api from '../lib/api'
import TelegramConnect from '../components/TelegramConnect'

const GOAL_MODES = [
    { value: 'lite', label: '🌱 Лайт', desc: '10 сообщений/день — минимальная активность' },
    { value: 'normal', label: '⚡ Нормал', desc: '20 сообщений/день — рекомендуется' },
    { value: 'hard', label: '🔥 Хард', desc: '40 сообщений/день — высокий риск' },
]

export default function Settings() {
    const { addNotification } = useStore()
    const [settings, setSettings] = useState<Record<string, string>>({})
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)
    const [apiKey, setApiKey] = useState('')
    const [quota, setQuota] = useState<any>(null)
    const [checkingKey, setCheckingKey] = useState(false)

    useEffect(() => {
        loadSettings()
    }, [])

    const loadSettings = async () => {
        try {
            const [settingsRes, quotaRes] = await Promise.all([
                settingsApi.getAll(),
                settingsApi.getQuota(),
            ])
            setSettings(settingsRes.data)
            setQuota(quotaRes.data)
        } catch (err) {
            console.error('Failed to load settings:', err)
        } finally {
            setLoading(false)
        }
    }

    const updateSetting = async (key: string, value: string) => {
        setSaving(true)
        try {
            const res = await settingsApi.update(key, value)
            setSettings({ ...settings, [key]: value })

            if (res.data.warning) {
                addNotification('info', res.data.warning)
            } else {
                addNotification('success', 'Настройка сохранена')
            }
        } catch (err: any) {
            addNotification('error', err.response?.data?.detail || 'Ошибка сохранения')
        } finally {
            setSaving(false)
        }
    }

    const saveApiKey = async () => {
        if (!apiKey.trim()) return
        await updateSetting('gemini_api_key', apiKey)
        setApiKey('')
    }

    const testGeminiConnection = async () => {
        setCheckingKey(true)
        try {
            const res = await api.get('/llm/test')
            if (res.data.status === 'ok') {
                addNotification('success', `Gemini работает! Ответ: ${res.data.message}`)
            } else {
                addNotification('error', `Ошибка Gemini: ${res.data.message}`)
            }
        } catch (err: any) {
            addNotification('error', 'Ошибка проверка соединения')
        } finally {
            setCheckingKey(false)
        }
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="animate-spin rounded-full h-12 w-12 border-4 border-white border-t-transparent"></div>
            </div>
        )
    }

    return (
        <div className="space-y-6 animate-fadeIn max-w-3xl">
            {/* Header */}
            <div>
                <h1 className="text-3xl font-bold text-white flex items-center gap-3">
                    ⚙️ Настройки
                </h1>
                <p className="text-white/70 mt-1">
                    Конфигурация приложения и лимитов
                </p>
            </div>

            {/* API Key */}
            <div className="card">
                <div className="flex items-center gap-3 mb-4">
                    <Key className="w-6 h-6 text-gray-600" />
                    <h2 className="text-lg font-bold text-gray-800">API Ключ Gemini</h2>
                </div>

                <p className="text-gray-600 text-sm mb-4">
                    Ключ нужен для работы AI-функций: классификация лидов, генерация сообщений, AI Coach.
                </p>

                {settings.gemini_api_key ? (
                    <div className="flex items-center gap-3 p-3 bg-green-50 rounded-lg mb-4">
                        <span className="text-green-700">✓ Ключ установлен: {settings.gemini_api_key}</span>
                    </div>
                ) : (
                    <div className="flex items-center gap-3 p-3 bg-yellow-50 rounded-lg mb-4">
                        <AlertTriangle className="w-5 h-5 text-yellow-600" />
                        <span className="text-yellow-700">Ключ не установлен — AI функции недоступны</span>
                    </div>
                )}

                <div className="flex gap-3">
                    <input
                        type="password"
                        value={apiKey}
                        onChange={(e) => setApiKey(e.target.value)}
                        placeholder="Введите новый API ключ"
                        className="flex-1 px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-500"
                    />
                    <button
                        onClick={saveApiKey}
                        disabled={!apiKey.trim() || saving}
                        className="btn-primary flex items-center gap-2"
                    >
                        <Save className="w-4 h-4" />
                        Сохранить
                    </button>
                    <button
                        onClick={testGeminiConnection}
                        disabled={checkingKey}
                        className="btn-secondary flex items-center gap-2"
                    >
                        {checkingKey ? <div className="w-4 h-4 animate-spin rounded-full border-2 border-white border-t-transparent" /> : <Shield className="w-4 h-4" />}
                        Проверить
                    </button>
                </div>

                <p className="text-xs text-gray-400 mt-2">
                    Получить ключ: <a href="https://aistudio.google.com/apikey" target="_blank" className="text-primary-500 hover:underline">Google AI Studio</a>
                </p>
            </div>

            {/* Telegram Connection */}
            <TelegramConnect />

            {/* Daily Limit */}
            <div className="card">
                <div className="flex items-center gap-3 mb-4">
                    <Shield className="w-6 h-6 text-gray-600" />
                    <h2 className="text-lg font-bold text-gray-800">Лимиты безопасности</h2>
                </div>

                <div className="space-y-6">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            Дневной лимит новых контактов
                        </label>
                        <div className="flex items-center gap-4">
                            <input
                                type="range"
                                min="5"
                                max="40"
                                value={settings.daily_limit || 15}
                                onChange={(e) => updateSetting('daily_limit', e.target.value)}
                                className="flex-1"
                            />
                            <span className="w-12 text-center font-bold text-gray-800">
                                {settings.daily_limit || 15}
                            </span>
                        </div>
                        <p className="text-xs text-gray-400 mt-1">
                            Рекомендуется: 15-25. Выше 25 — повышенный риск ограничений.
                        </p>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            Cooldown между follow-up (часы)
                        </label>
                        <div className="flex items-center gap-4">
                            <input
                                type="range"
                                min="12"
                                max="168"
                                step="12"
                                value={settings.followup_cooldown_hours || 48}
                                onChange={(e) => updateSetting('followup_cooldown_hours', e.target.value)}
                                className="flex-1"
                            />
                            <span className="w-16 text-center font-bold text-gray-800">
                                {settings.followup_cooldown_hours || 48}ч
                            </span>
                        </div>
                        <p className="text-xs text-gray-400 mt-1">
                            Минимальный интервал между сообщениями одному контакту.
                        </p>
                    </div>
                </div>

                {/* Current Quota */}
                {quota && (
                    <div className="mt-6 p-4 bg-gray-50 rounded-xl">
                        <div className="flex justify-between items-center mb-2">
                            <span className="text-gray-600">Отправлено сегодня</span>
                            <span className="font-bold">{quota.sent_today} / {quota.daily_limit}</span>
                        </div>
                        <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                            <div
                                className={`h-full rounded-full ${quota.usage_percent >= 80 ? 'bg-red-500' :
                                    quota.usage_percent >= 60 ? 'bg-yellow-500' : 'bg-green-500'
                                    }`}
                                style={{ width: `${quota.usage_percent}%` }}
                            />
                        </div>
                        {quota.warning && (
                            <p className="text-sm text-orange-600 mt-2">{quota.warning}</p>
                        )}
                    </div>
                )}
            </div>

            {/* Goal Mode */}
            <div className="card">
                <div className="flex items-center gap-3 mb-4">
                    <Target className="w-6 h-6 text-gray-600" />
                    <h2 className="text-lg font-bold text-gray-800">Режим целей</h2>
                </div>

                <div className="space-y-3">
                    {GOAL_MODES.map((mode) => (
                        <button
                            key={mode.value}
                            onClick={() => updateSetting('goal_mode', mode.value)}
                            className={`w-full flex items-center gap-4 p-4 rounded-xl transition-all ${settings.goal_mode === mode.value
                                ? 'bg-primary-100 border-2 border-primary-500'
                                : 'bg-gray-50 hover:bg-gray-100 border-2 border-transparent'
                                }`}
                        >
                            <span className="text-2xl">{mode.label.split(' ')[0]}</span>
                            <div className="text-left">
                                <div className="font-medium text-gray-800">{mode.label}</div>
                                <div className="text-sm text-gray-500">{mode.desc}</div>
                            </div>
                        </button>
                    ))}
                </div>

                {settings.goal_mode === 'hard' && (
                    <div className="mt-4 p-4 bg-orange-50 border border-orange-200 rounded-xl flex items-start gap-3">
                        <AlertTriangle className="w-5 h-5 text-orange-500 flex-shrink-0 mt-0.5" />
                        <div className="text-sm text-orange-700">
                            <strong>Внимание!</strong> Режим "Хард" предполагает высокую активность,
                            что может привести к ограничениям со стороны Telegram.
                            Рекомендуем использовать только при наличии "прогретого" аккаунта.
                        </div>
                    </div>
                )}
            </div>

            {/* About */}
            <div className="card">
                <h2 className="text-lg font-bold text-gray-800 mb-4">О приложении</h2>
                <div className="space-y-2 text-sm text-gray-600">
                    <p>TG Workspace v1.0.0</p>
                    <p>Десктоп-приложение для работы с лидами из Telegram</p>
                    <p className="text-xs text-gray-400 mt-4">
                        ⚠️ Приложение не отправляет сообщения автоматически.
                        Все сообщения отправляются вручную через Telegram.
                    </p>
                </div>
            </div>
        </div>
    )
}
