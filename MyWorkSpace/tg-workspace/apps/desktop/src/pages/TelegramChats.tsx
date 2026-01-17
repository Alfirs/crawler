import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
    MessageCircle, Download, RefreshCw, Copy,
    Search, Loader, Shield, Check, ExternalLink
} from 'lucide-react'
import { telegramApi } from '../lib/api'
import { useStore } from '../store/useStore'

interface Dialog {
    id: number
    name: string
    type: string
    unread_count: number
    last_message: string | null
    last_message_date: string | null
}

interface Message {
    id: number
    date: string
    text: string
    sender_id: number
    sender_name: string
    sender_username: string | null
    is_outgoing: boolean
}

export default function TelegramChats() {
    const { addNotification } = useStore()
    const navigate = useNavigate()

    const [dialogs, setDialogs] = useState<Dialog[]>([])
    const [selectedChat, setSelectedChat] = useState<Dialog | null>(null)
    const [messages, setMessages] = useState<Message[]>([])
    const [loading, setLoading] = useState(false)
    const [loadingMessages, setLoadingMessages] = useState(false)
    const [searchQuery, setSearchQuery] = useState('')
    const [draftMessage, setDraftMessage] = useState('')
    const [copied, setCopied] = useState(false)

    useEffect(() => {
        loadDialogs()
    }, [])

    const loadDialogs = async () => {
        setLoading(true)
        try {
            const res = await telegramApi.getDialogs(100)
            setDialogs(res.data.dialogs || [])
        } catch (err: any) {
            if (err.response?.status === 401) {
                addNotification('error', 'Telegram не подключен. Подключите в настройках.')
            } else {
                addNotification('error', 'Ошибка загрузки чатов')
            }
        } finally {
            setLoading(false)
        }
    }

    const loadMessages = async (chat: Dialog) => {
        setSelectedChat(chat)
        setLoadingMessages(true)
        try {
            const res = await telegramApi.getMessages(chat.id, 50)
            setMessages(res.data.messages || [])
        } catch (err) {
            addNotification('error', 'Ошибка загрузки сообщений')
        } finally {
            setLoadingMessages(false)
        }
    }

    const copyMessage = () => {
        if (!draftMessage.trim()) return
        navigator.clipboard.writeText(draftMessage)
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
        addNotification('success', 'Скопировано! Теперь вставьте в Telegram')
    }

    const openTelegram = () => {
        if (selectedChat) {
            // Try to open chat directly if it's a user
            const chatName = selectedChat.name
            if (chatName.startsWith('@')) {
                window.open(`https://t.me/${chatName.slice(1)}`, '_blank')
                return
            }
        }
        window.open('https://t.me/', '_blank')
    }

    const importChat = async (chatId: number) => {
        try {
            const res = await telegramApi.importFromChat(chatId, 100)
            addNotification('success', res.data.message)
        } catch (err) {
            addNotification('error', 'Ошибка импорта')
        }
    }

    const filteredDialogs = dialogs.filter(d =>
        d.name.toLowerCase().includes(searchQuery.toLowerCase())
    )

    const getChatIcon = (type: string) => {
        switch (type) {
            case 'user': return '👤'
            case 'group': return '👥'
            case 'channel': return '📢'
            default: return '💬'
        }
    }

    const formatDate = (dateStr: string | null) => {
        if (!dateStr) return ''
        const date = new Date(dateStr)
        const now = new Date()
        const isToday = date.toDateString() === now.toDateString()
        if (isToday) {
            return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
        }
        return date.toLocaleDateString('ru-RU', { day: '2-digit', month: 'short' })
    }

    return (
        <div className="space-y-6 animate-fadeIn">
            {/* Safety Banner - READ ONLY MODE */}
            <div className="glass rounded-xl p-4 flex items-center gap-3">
                <Shield className="w-6 h-6 text-green-400" />
                <div className="text-white">
                    <span className="font-medium">🔒 Режим только чтение:</span>
                    <span className="text-white/70 ml-2">
                        Приложение не отправляет сообщения. Только чтение и подготовка текстов.
                    </span>
                </div>
            </div>

            {/* Header */}
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold text-white flex items-center gap-3">
                        💬 Telegram чаты
                    </h1>
                    <p className="text-white/70 mt-1">
                        Чтение сообщений и подготовка ответов
                    </p>
                </div>
                <button onClick={loadDialogs} className="btn-secondary flex items-center gap-2">
                    <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                    Обновить
                </button>
            </div>

            <div className="grid grid-cols-3 gap-6" style={{ height: 'calc(100vh - 280px)' }}>
                {/* Dialogs List */}
                <div className="card overflow-hidden flex flex-col">
                    <div className="mb-4">
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                            <input
                                type="text"
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                placeholder="Поиск чатов..."
                                className="w-full pl-10 pr-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-500"
                            />
                        </div>
                    </div>

                    <div className="flex-1 overflow-auto space-y-2">
                        {loading ? (
                            <div className="flex justify-center py-8">
                                <Loader className="w-8 h-8 animate-spin text-gray-400" />
                            </div>
                        ) : filteredDialogs.length === 0 ? (
                            <div className="text-center py-8 text-gray-400">
                                Нет чатов
                            </div>
                        ) : (
                            filteredDialogs.map((dialog) => (
                                <div
                                    key={dialog.id}
                                    onClick={() => loadMessages(dialog)}
                                    className={`flex items-center gap-3 p-3 rounded-xl cursor-pointer transition-all ${selectedChat?.id === dialog.id
                                        ? 'bg-primary-100 border-2 border-primary-500'
                                        : 'hover:bg-gray-50'
                                        }`}
                                >
                                    <div className="text-2xl">{getChatIcon(dialog.type)}</div>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center justify-between">
                                            <span className="font-medium text-gray-800 truncate">{dialog.name}</span>
                                            {dialog.unread_count > 0 && (
                                                <span className="bg-primary-500 text-white text-xs px-2 py-0.5 rounded-full">
                                                    {dialog.unread_count}
                                                </span>
                                            )}
                                        </div>
                                        <p className="text-sm text-gray-500 truncate">
                                            {dialog.last_message || 'Нет сообщений'}
                                        </p>
                                    </div>
                                    <div className="text-xs text-gray-400">
                                        {formatDate(dialog.last_message_date)}
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>

                {/* Messages / Chat View */}
                <div className="col-span-2 card overflow-hidden flex flex-col">
                    {selectedChat ? (
                        <>
                            {/* Chat Header */}
                            <div className="flex items-center justify-between pb-4 border-b mb-4">
                                <div className="flex items-center gap-3">
                                    <span className="text-2xl">{getChatIcon(selectedChat.type)}</span>
                                    <div>
                                        <h3 className="font-bold text-gray-800">{selectedChat.name}</h3>
                                        <span className="text-sm text-gray-500">{selectedChat.type}</span>
                                    </div>
                                </div>
                                <button
                                    onClick={() => importChat(selectedChat.id)}
                                    className="btn-ghost flex items-center gap-2 text-primary-600"
                                >
                                    <Download className="w-4 h-4" />
                                    Импорт в лиды
                                </button>
                            </div>

                            {/* Messages */}
                            <div className="flex-1 overflow-auto space-y-3 mb-4">
                                {loadingMessages ? (
                                    <div className="flex justify-center py-8">
                                        <Loader className="w-8 h-8 animate-spin text-gray-400" />
                                    </div>
                                ) : messages.length === 0 ? (
                                    <div className="text-center py-8 text-gray-400">
                                        Нет сообщений
                                    </div>
                                ) : (
                                    [...messages].reverse().map((msg) => (
                                        <div
                                            key={msg.id}
                                            className={`flex ${msg.is_outgoing ? 'justify-end' : 'justify-start'}`}
                                        >
                                            <div
                                                className={`max-w-[70%] p-3 rounded-2xl ${msg.is_outgoing
                                                    ? 'bg-primary-500 text-white rounded-br-sm'
                                                    : 'bg-gray-100 text-gray-800 rounded-bl-sm'
                                                    }`}
                                            >
                                                {!msg.is_outgoing && (
                                                    <div className="text-xs font-medium text-primary-600 mb-1">
                                                        {msg.sender_name}
                                                        {msg.sender_username && ` @${msg.sender_username}`}
                                                    </div>
                                                )}
                                                <p className="whitespace-pre-wrap">{msg.text}</p>
                                                <div className={`text-xs mt-1 ${msg.is_outgoing ? 'text-white/70' : 'text-gray-400'}`}>
                                                    {formatDate(msg.date)}
                                                </div>
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>

                            {/* Draft Message Area - NO SEND, ONLY COPY */}
                            <div className="pt-4 border-t">
                                <div className="flex items-center gap-2 mb-3 text-sm text-gray-500">
                                    <Shield className="w-4 h-4 text-green-500" />
                                    Напишите ответ здесь, затем скопируйте и вставьте в Telegram
                                </div>
                                <div className="flex gap-3">
                                    <textarea
                                        value={draftMessage}
                                        onChange={(e) => setDraftMessage(e.target.value)}
                                        placeholder="Подготовьте ответ здесь..."
                                        className="flex-1 px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-500 resize-none"
                                        rows={2}
                                    />
                                </div>
                                <div className="flex gap-3 mt-3">
                                    <button
                                        onClick={copyMessage}
                                        disabled={!draftMessage.trim()}
                                        className="btn-primary flex items-center gap-2"
                                    >
                                        {copied ? (
                                            <>
                                                <Check className="w-5 h-5" />
                                                Скопировано!
                                            </>
                                        ) : (
                                            <>
                                                <Copy className="w-5 h-5" />
                                                Копировать текст
                                            </>
                                        )}
                                    </button>
                                    <button
                                        onClick={openTelegram}
                                        className="btn-secondary flex items-center gap-2"
                                    >
                                        <ExternalLink className="w-5 h-5" />
                                        Открыть Telegram
                                    </button>
                                </div>
                            </div>
                        </>
                    ) : (
                        <div className="flex-1 flex items-center justify-center text-gray-400">
                            <div className="text-center">
                                <MessageCircle className="w-16 h-16 mx-auto mb-4 opacity-30" />
                                <p>Выберите чат слева</p>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
