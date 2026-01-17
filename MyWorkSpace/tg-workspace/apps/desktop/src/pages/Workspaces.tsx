import { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
    Plus, Upload, Trash2, FolderOpen, FileJson, Link,
    ChevronRight, Loader, CheckCircle, Smartphone, AlertCircle, Download
} from 'lucide-react'
import { useStore } from '../store/useStore'
import { workspacesApi, sourcesApi, jobsApi } from '../lib/api'

interface Workspace {
    id: number
    name: string
    description?: string
    sources_count: number
    leads_count: number
    created_at: string
}

interface Source {
    id: number
    type: string
    title: string
    message_count: number
    parsed_at?: string
}

interface Job {
    id: number
    status: 'pending' | 'processing' | 'completed' | 'failed'
    progress: number
    total_items: number
    processed_items: number
    message: string
    error?: string
    result?: any
}

export default function Workspaces() {
    const { currentWorkspace, setCurrentWorkspace, addNotification } = useStore()
    const navigate = useNavigate()
    const fileInputRef = useRef<HTMLInputElement>(null)

    const [workspaces, setWorkspaces] = useState<Workspace[]>([])
    const [sources, setSources] = useState<Source[]>([])
    const [loading, setLoading] = useState(true)
    const [showCreateModal, setShowCreateModal] = useState(false)
    const [newWorkspaceName, setNewWorkspaceName] = useState('')

    // Import Modal State
    const [showImportModal, setShowImportModal] = useState(false)
    const [importLink, setImportLink] = useState('')
    const [importLimit, setImportLimit] = useState(100)
    const [importSinceDate, setImportSinceDate] = useState('')
    const [autoClassify, setAutoClassify] = useState(true)

    // activeJob replaces simple loading states
    const [activeJob, setActiveJob] = useState<Job | null>(null)

    useEffect(() => {
        loadWorkspaces()
    }, [])

    useEffect(() => {
        if (currentWorkspace) {
            loadSources()
        }
    }, [currentWorkspace])

    const loadWorkspaces = async () => {
        try {
            const res = await workspacesApi.list()
            setWorkspaces(res.data)

            if (res.data.length > 0 && !currentWorkspace) {
                setCurrentWorkspace(res.data[0])
            }
        } catch (err) {
            console.error('Failed to load workspaces:', err)
        } finally {
            setLoading(false)
        }
    }

    const loadSources = async () => {
        if (!currentWorkspace) return
        try {
            const res = await sourcesApi.list(currentWorkspace.id)
            setSources(res.data)
        } catch (err) {
            console.error('Failed to load sources:', err)
        }
    }

    const createWorkspace = async () => {
        if (!newWorkspaceName.trim()) return

        try {
            const res = await workspacesApi.create({ name: newWorkspaceName })
            setWorkspaces([res.data, ...workspaces])
            setCurrentWorkspace(res.data)
            setNewWorkspaceName('')
            setShowCreateModal(false)
            addNotification('success', 'Воркспейс создан!')
        } catch (err) {
            addNotification('error', 'Ошибка создания воркспейса')
        }
    }

    const deleteWorkspace = async (id: number) => {
        if (!confirm('Удалить воркспейс и все его данные?')) return

        try {
            await workspacesApi.delete(id)
            setWorkspaces(workspaces.filter(w => w.id !== id))
            if (currentWorkspace?.id === id) {
                setCurrentWorkspace(workspaces.find(w => w.id !== id) || null)
            }
            addNotification('success', 'Воркспейс удален')
        } catch (err) {
            addNotification('error', 'Ошибка удаления')
        }
    }

    // --- Job Polling Logic ---
    const pollJob = async (jobId: number, onSuccess: (result: any) => void) => {
        const interval = setInterval(async () => {
            try {
                const res = await jobsApi.get(jobId)
                const job = res.data
                setActiveJob(job)

                if (job.status === 'completed') {
                    clearInterval(interval)
                    setActiveJob(null)
                    onSuccess(job.result)
                } else if (job.status === 'failed') {
                    clearInterval(interval)
                    setActiveJob(null)
                    addNotification('error', `Ошибка: ${job.error || 'Неизвестная ошибка'}`)
                }
            } catch (err) {
                console.error('Poll error:', err)
                clearInterval(interval)
                setActiveJob(null)
                addNotification('error', 'Ошибка проверки статуса задачи')
            }
        }, 1000)
    }

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files
        if (!files || files.length === 0 || !currentWorkspace) return

        const file = files[0] // Only support 1 file for now with job system for simplicity

        try {
            const title = file.name.replace(/\.(json|html?)$/i, '')
            // API now starts a background job
            const res = await sourcesApi.uploadFile(currentWorkspace.id, title, file)
            const { job_id } = res.data

            // Start polling
            setActiveJob({
                id: job_id,
                status: 'pending',
                progress: 0,
                total_items: 0,
                processed_items: 0,
                message: 'Загрузка файла...'
            })

            pollJob(job_id, async (result) => {
                addNotification('success', `Файл загружен: ${result.message_count} сообщений`)
                loadSources()
                // Refresh workspace stats
                const wsRes = await workspacesApi.get(currentWorkspace.id)
                setCurrentWorkspace(wsRes.data)
            })

        } catch (err: any) {
            addNotification('error', `Ошибка запуска: ${err.response?.data?.detail || 'Неизвестная ошибка'}`)
        }

        if (fileInputRef.current) {
            fileInputRef.current.value = ''
        }
    }

    const handleLinkImport = async () => {
        if (!currentWorkspace || !importLink.trim()) return

        try {
            setShowImportModal(false)

            // Format date correctly if exists
            let sinceDateIso = undefined
            if (importSinceDate) {
                sinceDateIso = new Date(importSinceDate).toISOString()
            }

            const res = await sourcesApi.importLink(
                currentWorkspace.id,
                importLink,
                importLimit,
                sinceDateIso,
                autoClassify
            )
            const { job_id } = res.data

            setActiveJob({
                id: job_id,
                status: 'pending',
                progress: 0,
                total_items: importLimit,
                processed_items: 0,
                message: 'Подключение к Telegram...'
            })

            pollJob(job_id, async (result) => {
                const msg = autoClassify
                    ? `Импорт завершен: ${result.message_count} сообщений. Лиды созданы.`
                    : `Импорт завершен: ${result.message_count} сообщений`
                addNotification('success', msg)
                loadSources()
                setImportLink('')
                setImportLimit(100)
                setImportSinceDate('')
                // Refresh workspace stats
                if (currentWorkspace) {
                    const wsRes = await workspacesApi.get(currentWorkspace.id)
                    setCurrentWorkspace(wsRes.data)
                }
            })

        } catch (err: any) {
            addNotification('error', `Ошибка запуска импорта: ${err.response?.data?.detail || 'Неизвестная ошибка'}`)
        }
    }

    const classifySource = async (sourceId: number) => {
        try {
            const res = await sourcesApi.classify(sourceId)
            const { job_id } = res.data

            setActiveJob({
                id: job_id,
                status: 'pending',
                progress: 0,
                total_items: 0,
                processed_items: 0,
                message: 'Поиск лидов...'
            })

            pollJob(job_id, async (result) => {
                addNotification('success', `Обработано: ${result.classified}, Найдено лидов: ${result.leads_created}`)
                // Refresh stats
                if (currentWorkspace) {
                    const wsRes = await workspacesApi.get(currentWorkspace.id)
                    setCurrentWorkspace(wsRes.data)
                }
            })

        } catch (err) {
            addNotification('error', 'Ошибка запуска классификации')
        }
    }

    const deleteSource = async (sourceId: number) => {
        if (!confirm('Удалить источник и все сообщения?')) return

        try {
            await sourcesApi.delete(sourceId)
            setSources(sources.filter(s => s.id !== sourceId))
            addNotification('success', 'Источник удален')
        } catch (err) {
            addNotification('error', 'Ошибка удаления')
        }
    }

    return (
        <div className="space-y-8 animate-fadeIn relative">
            {/* Header */}
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold text-white flex items-center gap-3">
                        📁 Воркспейсы
                    </h1>
                    <p className="text-white/70 mt-1">
                        Управление проектами и источниками данных
                    </p>
                </div>
                <button
                    onClick={() => setShowCreateModal(true)}
                    className="btn-primary flex items-center gap-2"
                >
                    <Plus className="w-5 h-5" />
                    Новый воркспейс
                </button>
            </div>

            <div className="grid grid-cols-3 gap-6">
                {/* Workspace List */}
                <div className="card">
                    <h2 className="text-lg font-bold text-gray-800 mb-4">Мои воркспейсы</h2>

                    {loading ? (
                        <div className="flex justify-center py-8">
                            <Loader className="w-8 h-8 animate-spin text-gray-400" />
                        </div>
                    ) : workspaces.length === 0 ? (
                        <div className="text-center py-8 text-gray-400">
                            <FolderOpen className="w-12 h-12 mx-auto mb-2 opacity-50" />
                            <p>Нет воркспейсов</p>
                        </div>
                    ) : (
                        <div className="space-y-2">
                            {workspaces.map((ws) => (
                                <div
                                    key={ws.id}
                                    onClick={() => setCurrentWorkspace(ws)}
                                    className={`flex items-center justify-between p-4 rounded-xl cursor-pointer transition-all ${currentWorkspace?.id === ws.id
                                        ? 'bg-primary-100 border-2 border-primary-500'
                                        : 'bg-gray-50 hover:bg-gray-100'
                                        }`}
                                >
                                    <div className="flex items-center gap-3">
                                        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${currentWorkspace?.id === ws.id ? 'bg-primary-500 text-white' : 'bg-gray-200'
                                            }`}>
                                            📁
                                        </div>
                                        <div>
                                            <div className="font-medium text-gray-800">{ws.name}</div>
                                            <div className="text-sm text-gray-500">
                                                {ws.sources_count} источников · {ws.leads_count} лидов
                                            </div>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation()
                                                deleteWorkspace(ws.id)
                                            }}
                                            className="p-2 hover:bg-red-100 rounded-lg text-gray-400 hover:text-red-500"
                                        >
                                            <Trash2 className="w-4 h-4" />
                                        </button>
                                        <ChevronRight className="w-5 h-5 text-gray-300" />
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Sources Panel */}
                <div className="col-span-2">
                    {currentWorkspace ? (
                        <div className="card">
                            <div className="flex items-center justify-between mb-6">
                                <div>
                                    <h2 className="text-xl font-bold text-gray-800">{currentWorkspace.name}</h2>
                                    <p className="text-gray-500 text-sm">{currentWorkspace.description || 'Нет описания'}</p>
                                </div>
                                <div className="flex gap-3">
                                    <button
                                        onClick={() => setShowImportModal(true)}
                                        disabled={!!activeJob}
                                        className="btn-ghost flex items-center gap-2 border border-primary-200 text-primary-700 hover:bg-primary-50"
                                    >
                                        <Link className="w-5 h-5" />
                                        Импорт по ссылке
                                    </button>

                                    <input
                                        ref={fileInputRef}
                                        type="file"
                                        accept=".json,.html"
                                        onChange={handleFileUpload}
                                        className="hidden"
                                    />
                                    <button
                                        onClick={() => fileInputRef.current?.click()}
                                        disabled={!!activeJob}
                                        className="btn-primary flex items-center gap-2"
                                    >
                                        <Upload className="w-5 h-5" />
                                        Загрузить экспорт
                                    </button>
                                </div>
                            </div>

                            {/* Upload Instructions */}
                            <div className="bg-blue-50 rounded-xl p-4 mb-6">
                                <h3 className="font-medium text-blue-800 mb-2">📥 Как загрузить экспорт Telegram</h3>
                                <p className="text-sm text-blue-700">Перетяните result.json или нажмите "Загрузить экспорт". Чтобы добавить историю чата по ссылке, нажмите "Импорт по ссылке".</p>
                            </div>

                            {/* Sources List */}
                            <h3 className="font-bold text-gray-800 mb-4">Источники данных</h3>
                            {sources.length === 0 ? (
                                <div className="text-center py-8 text-gray-400 bg-gray-50 rounded-xl">
                                    <FileJson className="w-12 h-12 mx-auto mb-2 opacity-50" />
                                    <p>Загрузите первый экспорт чата</p>
                                </div>
                            ) : (
                                <div className="space-y-3">
                                    {sources.map((source) => (
                                        <div
                                            key={source.id}
                                            className="flex items-center justify-between p-4 bg-gray-50 rounded-xl"
                                        >
                                            <div className="flex items-center gap-3">
                                                <div className="w-10 h-10 rounded-lg bg-gray-200 flex items-center justify-center">
                                                    {source.type.includes('json') ? (
                                                        <FileJson className="w-5 h-5 text-gray-600" />
                                                    ) : source.type === 'link' || source.type === 'telegram_import' ? (
                                                        <Link className="w-5 h-5 text-gray-600" />
                                                    ) : (
                                                        <FileJson className="w-5 h-5 text-gray-600" />
                                                    )}
                                                </div>
                                                <div>
                                                    <div className="font-medium text-gray-800">{source.title}</div>
                                                    <div className="text-sm text-gray-500">
                                                        {source.message_count} сообщений
                                                        {source.parsed_at && ' · Обработан'}
                                                        {source.link && <span className="text-blue-500 ml-2 text-xs">{source.link}</span>}
                                                    </div>
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <button
                                                    onClick={() => classifySource(source.id)}
                                                    disabled={!!activeJob}
                                                    className="btn-ghost flex items-center gap-1 text-primary-600"
                                                >
                                                    <CheckCircle className="w-4 h-4" />
                                                    Найти лиды
                                                </button>
                                                <button
                                                    onClick={() => deleteSource(source.id)}
                                                    className="p-2 hover:bg-red-100 rounded-lg text-gray-400 hover:text-red-500"
                                                >
                                                    <Trash2 className="w-4 h-4" />
                                                </button>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}

                            {/* View Leads Button */}
                            {currentWorkspace.leads_count > 0 && (
                                <button
                                    onClick={() => navigate('/leads')}
                                    className="mt-6 w-full btn-primary"
                                >
                                    Открыть {currentWorkspace.leads_count} лидов →
                                </button>
                            )}
                        </div>
                    ) : (
                        <div className="card text-center py-12">
                            <FolderOpen className="w-16 h-16 mx-auto text-gray-300 mb-4" />
                            <h3 className="text-xl font-bold text-gray-700 mb-2">Выберите воркспейс</h3>
                            <p className="text-gray-500">Или создайте новый для начала работы</p>
                        </div>
                    )}
                </div>
            </div>

            {/* Job Progress Modal */}
            {activeJob && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <div className="bg-white rounded-2xl p-6 w-96 animate-fadeIn shadow-2xl">
                        <div className="flex flex-col items-center text-center">
                            <div className="w-16 h-16 bg-blue-50 rounded-full flex items-center justify-center mb-4">
                                <Loader className="w-8 h-8 text-blue-500 animate-spin" />
                            </div>
                            <h2 className="text-xl font-bold text-gray-800 mb-2">
                                {activeJob.type === 'upload_source' ? 'Загрузка файла' :
                                    activeJob.type === 'import_history' ? 'Импорт истории' : 'Поиск лидов'}
                            </h2>
                            <p className="text-gray-500 mb-6">
                                {activeJob.message || 'Обработка данных...'}
                            </p>

                            {/* Progress Bar */}
                            <div className="w-full h-3 bg-gray-100 rounded-full overflow-hidden mb-2">
                                <div
                                    className="h-full bg-blue-500 transition-all duration-300"
                                    style={{ width: `${activeJob.progress}%` }}
                                />
                            </div>
                            <div className="flex justify-between w-full text-sm text-gray-500">
                                <span>{activeJob.progress}%</span>
                                {activeJob.total_items > 0 && (
                                    <span>{activeJob.processed_items} / {activeJob.total_items}</span>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Create Workspace Modal */}
            {showCreateModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <div className="bg-white rounded-2xl p-6 w-96 animate-fadeIn">
                        <h2 className="text-xl font-bold text-gray-800 mb-4">Новый воркспейс</h2>
                        <input
                            type="text"
                            value={newWorkspaceName}
                            onChange={(e) => setNewWorkspaceName(e.target.value)}
                            placeholder="Название воркспейса"
                            className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-500 mb-4"
                            autoFocus
                        />
                        <div className="flex gap-3">
                            <button
                                onClick={() => setShowCreateModal(false)}
                                className="flex-1 btn-ghost"
                            >
                                Отмена
                            </button>
                            <button
                                onClick={createWorkspace}
                                disabled={!newWorkspaceName.trim()}
                                className="flex-1 btn-primary"
                            >
                                Создать
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Import Link Modal */}
            {showImportModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <div className="bg-white rounded-2xl p-6 w-96 animate-fadeIn">
                        <h2 className="text-xl font-bold text-gray-800 mb-4 flex items-center gap-2">
                            <Link className="w-6 h-6 text-primary-500" />
                            Импорт из Telegram
                        </h2>

                        <div className="space-y-4 mb-6">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Ссылка или юзернейм</label>
                                <input
                                    type="text"
                                    value={importLink}
                                    onChange={(e) => setImportLink(e.target.value)}
                                    placeholder="https://t.me/chat_name или @username"
                                    className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-500"
                                    autoFocus
                                />
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Кол-во сообщений</label>
                                    <input
                                        type="number"
                                        value={importLimit}
                                        onChange={(e) => setImportLimit(Number(e.target.value))}
                                        min="10"
                                        max="5000"
                                        className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-500"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Начиная с даты</label>
                                    <input
                                        type="date"
                                        value={importSinceDate}
                                        onChange={(e) => setImportSinceDate(e.target.value)}
                                        className="w-full px-4 py-2 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-500"
                                    />
                                </div>
                            </div>

                            <div className="bg-blue-50 p-3 rounded-lg text-sm text-blue-700 flex items-start gap-2">
                                <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                                <p>Бот вступит в чат (если это возможно) и скачает историю сообщений для поиска лидов.</p>
                            </div>

                            {/* Auto-classify checkbox */}
                            <label className="flex items-center gap-3 cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={autoClassify}
                                    onChange={(e) => setAutoClassify(e.target.checked)}
                                    className="w-5 h-5 rounded border-gray-300 text-primary-500 focus:ring-primary-500"
                                />
                                <span className="text-sm text-gray-700">
                                    <span className="font-medium">Авто-классификация</span>
                                    <span className="text-gray-500 ml-1">(найти лиды сразу после импорта)</span>
                                </span>
                            </label>
                        </div>

                        <div className="flex gap-3">
                            <button
                                onClick={() => setShowImportModal(false)}
                                className="flex-1 btn-ghost"
                            >
                                Отмена
                            </button>
                            <button
                                onClick={handleLinkImport}
                                disabled={!importLink.trim()}
                                className="flex-1 btn-primary"
                            >
                                Начать импорт
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
