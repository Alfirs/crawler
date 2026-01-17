import { useState, useEffect } from 'react'
import {
    Smartphone, Key, Check, Loader, LogOut, MessageCircle,
    AlertTriangle, RefreshCw
} from 'lucide-react'
import QRCode from 'react-qr-code'
import { telegramApi } from '../lib/api'
import { useStore } from '../store/useStore'

type AuthStep = 'init' | 'phone' | 'qr' | 'code' | '2fa' | 'success'

export default function TelegramConnect() {
    const { addNotification } = useStore()
    const [step, setStep] = useState<AuthStep>('init')
    const [loading, setLoading] = useState(false)
    const [authStatus, setAuthStatus] = useState<any>(null)

    // Form data
    const [apiId, setApiId] = useState('')
    const [apiHash, setApiHash] = useState('')
    const [phone, setPhone] = useState('')
    const [code, setCode] = useState('')
    const [password, setPassword] = useState('')

    // QR State
    const [qrUrl, setQrUrl] = useState('')
    const [qrStatus, setQrStatus] = useState('')

    useEffect(() => {
        checkAuthStatus()
    }, [])

    const checkAuthStatus = async () => {
        try {
            const res = await telegramApi.getAuthStatus()
            setAuthStatus(res.data)
            if (res.data.authorized) {
                setStep('success')
            }
        } catch (err) {
            // Not initialized yet
            setStep('init')
        }
    }

    // QR Polling
    useEffect(() => {
        let interval: NodeJS.Timeout

        if (step === 'qr' && qrUrl) {
            interval = setInterval(async () => {
                try {
                    const res = await telegramApi.checkQrAuth()
                    if (res.data.status === 'authorized') {
                        setAuthStatus(res.data)
                        setStep('success')
                        addNotification('success', `Успешный вход: ${res.data.user?.username}`)
                    } else if (res.data.status === '2fa_required') {
                        setStep('2fa')
                        addNotification('warning', 'Требуется пароль облачной защиты')
                    } else if (res.data.status === 'expired') {
                        setQrStatus('expired')
                        addNotification('warning', 'QR код истек, генерируем новый...')
                        handleQrInit()
                    }
                } catch (err) {
                    // Ignore polling errors
                }
            }, 2000)
        }

        return () => clearInterval(interval)
    }, [step, qrUrl])

    const handleInit = async () => {
        if (!apiId || !apiHash) {
            addNotification('error', 'Введите API ID и API Hash')
            return
        }

        setLoading(true)
        try {
            const res = await telegramApi.init(parseInt(apiId), apiHash)
            if (res.data.authorized) {
                setStep('success')
                addNotification('success', 'Telegram подключен!')
            } else {
                setStep('phone')
            }
        } catch (err: any) {
            addNotification('error', err.response?.data?.detail || 'Ошибка инициализации')
        } finally {
            setLoading(false)
        }
    }

    const handleQrInit = async () => {
        setLoading(true)
        setStep('qr')
        setQrStatus('loading')
        try {
            const res = await telegramApi.getQrCode()
            if (res.data.status === 'qr_generated') {
                setQrUrl(res.data.url)
                setQrStatus('ready')
            } else {
                addNotification('error', 'Ошибка генерации QR')
            }
        } catch (err) {
            addNotification('error', 'Ошибка запроса QR')
        } finally {
            setLoading(false)
        }
    }

    const handlePhone = async () => {
        if (!phone) {
            addNotification('error', 'Введите номер телефона')
            return
        }

        setLoading(true)
        try {
            const res = await telegramApi.startAuth(phone)
            if (res.data.status === 'code_sent') {
                setStep('code')
                addNotification('success', 'Код отправлен в Telegram')
            } else {
                addNotification('error', res.data.message)
            }
        } catch (err: any) {
            addNotification('error', err.response?.data?.detail || 'Ошибка')
        } finally {
            setLoading(false)
        }
    }

    const handleCode = async () => {
        if (!code) {
            addNotification('error', 'Введите код')
            return
        }

        setLoading(true)
        try {
            const res = await telegramApi.verifyCode(code)
            if (res.data.status === 'authorized') {
                setStep('success')
                setAuthStatus(res.data)
                addNotification('success', `Добро пожаловать, ${res.data.user?.first_name}!`)
            } else if (res.data.status === '2fa_required') {
                setStep('2fa')
            } else {
                addNotification('error', res.data.message)
            }
        } catch (err: any) {
            addNotification('error', err.response?.data?.detail || 'Неверный код')
        } finally {
            setLoading(false)
        }
    }

    const handle2fa = async () => {
        if (!password) {
            addNotification('error', 'Введите пароль')
            return
        }

        setLoading(true)
        try {
            const res = await telegramApi.verify2fa(password)
            if (res.data.status === 'authorized') {
                setStep('success')
                setAuthStatus(res.data)
                addNotification('success', 'Авторизация успешна!')
            } else {
                addNotification('error', res.data.message)
            }
        } catch (err: any) {
            addNotification('error', err.response?.data?.detail || 'Неверный пароль')
        } finally {
            setLoading(false)
        }
    }

    const handleLogout = async () => {
        if (!confirm('Отключить Telegram аккаунт?')) return

        setLoading(true)
        try {
            await telegramApi.logout()
            setStep('init')
            setAuthStatus(null)
            addNotification('success', 'Telegram отключен')
        } catch (err) {
            addNotification('error', 'Ошибка выхода')
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="card">
            <div className="flex items-center gap-3 mb-6">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-r from-blue-500 to-cyan-500 flex items-center justify-center">
                    <MessageCircle className="w-6 h-6 text-white" />
                </div>
                <div>
                    <h2 className="text-lg font-bold text-gray-800">Telegram подключение</h2>
                    <p className="text-sm text-gray-500">
                        {step === 'success' ? 'Подключено' : 'Для работы в реальном времени'}
                    </p>
                </div>
            </div>

            {/* Step: Init - API Credentials */}
            {step === 'init' && (
                <div className="space-y-4">
                    <div className="p-4 bg-blue-50 rounded-xl text-sm text-blue-700">
                        <p className="font-medium mb-2">📋 Как получить API credentials:</p>
                        <ol className="space-y-1 ml-4">
                            <li>1. Откройте <a href="https://my.telegram.org" target="_blank" className="underline">my.telegram.org</a></li>
                            <li>2. Войдите по номеру телефона</li>
                            <li>3. Перейдите в "API development tools"</li>
                            <li>4. Создайте приложение → скопируйте API ID и Hash</li>
                        </ol>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">API ID</label>
                        <input
                            type="text"
                            value={apiId}
                            onChange={(e) => setApiId(e.target.value)}
                            placeholder="12345678"
                            className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-500"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">API Hash</label>
                        <input
                            type="password"
                            value={apiHash}
                            onChange={(e) => setApiHash(e.target.value)}
                            placeholder="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                            className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-500"
                        />
                    </div>

                    <button onClick={handleInit} disabled={loading} className="w-full btn-primary flex items-center justify-center gap-2">
                        {loading ? <Loader className="w-5 h-5 animate-spin" /> : <Key className="w-5 h-5" />}
                        Подключить
                    </button>
                </div>
            )}

            {/* Step: Auth Method Selection */}
            {(step === 'phone' || step === 'qr') && (
                <div className="flex bg-gray-100 p-1 rounded-lg mb-4">
                    <button
                        onClick={() => setStep('phone')}
                        className={`flex-1 py-1.5 text-sm rounded-md transition-all ${step === 'phone' ? 'bg-white shadow text-blue-600 font-medium' : 'text-gray-500'}`}
                    >
                        По номеру
                    </button>
                    <button
                        onClick={handleQrInit}
                        className={`flex-1 py-1.5 text-sm rounded-md transition-all ${step === 'qr' ? 'bg-white shadow text-blue-600 font-medium' : 'text-gray-500'}`}
                    >
                        По QR коду
                    </button>
                </div>
            )}

            {/* Step: Phone */}
            {step === 'phone' && (
                <div className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Номер телефона</label>
                        <input
                            type="tel"
                            value={phone}
                            onChange={(e) => setPhone(e.target.value)}
                            placeholder="+7 900 123 45 67"
                            className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-500"
                        />
                    </div>

                    <button onClick={handlePhone} disabled={loading} className="w-full btn-primary flex items-center justify-center gap-2">
                        {loading ? <Loader className="w-5 h-5 animate-spin" /> : <Smartphone className="w-5 h-5" />}
                        Получить код
                    </button>
                </div>
            )}

            {/* Step: QR */}
            {step === 'qr' && (
                <div className="space-y-4 text-center">
                    <div className="p-4 bg-white rounded-xl border border-gray-100 shadow-sm flex flex-col items-center justify-center min-h-[250px]">
                        {loading ? (
                            <Loader className="w-8 h-8 animate-spin text-blue-500" />
                        ) : qrUrl ? (
                            <div className="p-2 bg-white rounded-lg">
                                <QRCode value={qrUrl} size={200} />
                            </div>
                        ) : (
                            <div className="text-gray-400">Не удалось загрузить QR</div>
                        )}

                        <p className="mt-4 text-sm text-gray-500">
                            1. Откройте Telegram на телефоне<br />
                            2. Настройки → Устройства → Подключить<br />
                            3. Отсканируйте код
                        </p>
                    </div>
                </div>
            )}

            {/* Step: Code */}
            {step === 'code' && (
                <div className="space-y-4">
                    <div className="p-4 bg-green-50 rounded-xl text-green-700 text-sm">
                        ✅ Код отправлен на ваш Telegram
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Код подтверждения</label>
                        <input
                            type="text"
                            value={code}
                            onChange={(e) => setCode(e.target.value)}
                            placeholder="12345"
                            className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-500 text-center text-2xl tracking-widest"
                            maxLength={5}
                            autoFocus
                        />
                    </div>

                    <button onClick={handleCode} disabled={loading} className="w-full btn-primary flex items-center justify-center gap-2">
                        {loading ? <Loader className="w-5 h-5 animate-spin" /> : <Check className="w-5 h-5" />}
                        Подтвердить
                    </button>
                </div>
            )}

            {/* Step: 2FA */}
            {step === '2fa' && (
                <div className="space-y-4">
                    <div className="p-4 bg-yellow-50 rounded-xl text-yellow-700 text-sm flex items-start gap-2">
                        <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" />
                        <span>Требуется пароль двухфакторной аутентификации</span>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Пароль 2FA</label>
                        <input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="Ваш облачный пароль"
                            className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-500"
                            autoFocus
                        />
                    </div>

                    <button onClick={handle2fa} disabled={loading} className="w-full btn-primary flex items-center justify-center gap-2">
                        {loading ? <Loader className="w-5 h-5 animate-spin" /> : <Check className="w-5 h-5" />}
                        Войти
                    </button>
                </div>
            )}

            {/* Step: Success */}
            {step === 'success' && authStatus?.user && (
                <div className="space-y-4">
                    <div className="p-4 bg-green-50 rounded-xl flex items-center gap-4">
                        <div className="w-12 h-12 rounded-full bg-green-500 flex items-center justify-center text-white text-xl">
                            ✓
                        </div>
                        <div>
                            <div className="font-bold text-gray-800">
                                {authStatus.user.first_name} {authStatus.user.last_name || ''}
                            </div>
                            <div className="text-sm text-gray-500">
                                @{authStatus.user.username || 'без username'}
                            </div>
                        </div>
                    </div>

                    <div className="flex gap-3">
                        <button onClick={checkAuthStatus} className="flex-1 btn-ghost flex items-center justify-center gap-2">
                            <RefreshCw className="w-4 h-4" />
                            Обновить
                        </button>
                        <button onClick={handleLogout} disabled={loading} className="flex-1 btn-ghost text-red-500 flex items-center justify-center gap-2">
                            <LogOut className="w-4 h-4" />
                            Отключить
                        </button>
                    </div>
                </div>
            )}
        </div>
    )
}
