import { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
    Plus, Upload, Trash2, FolderOpen, FileJson, Link,
    ChevronRight, Loader, CheckCircle
} from 'lucide-react'
import { useStore } from '../store/useStore'
import { workspacesApi, sourcesApi } from '../lib/api'

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

export default function Workspaces() {
    const { currentWorkspace, setCurrentWorkspace, addNotification } = useStore()
    const navigate = useNavigate()
    const fileInputRef = useRef<HTMLInputElement>(null)

    const [workspaces, setWorkspaces] = useState<Workspace[]>([])
    const [sources, setSources] = useState<Source[]>([])
    const [loading, setLoading] = useState(true)
    const [showCreateModal, setShowCreateModal] = useState(false)
    const [newWorkspaceName, setNewWorkspaceName] = useState('')
    const [uploading, setUploading] = useState(false)
    const [uploadProgress, setUploadProgress] = useState({ current: 0, total: 0 })
    const [classifying, setClassifying] = useState<number | null>(null)

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

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files
        if (!files || files.length === 0 || !currentWorkspace) return

        const fileArray = Array.from(files)
        setUploading(true)
        setUploadProgress({ current: 0, total: fileArray.length })

        let successCount = 0
        let totalMessages = 0
        const newSources: Source[] = []

        for (let i = 0; i < fileArray.length; i++) {
            const file = fileArray[i]
            setUploadProgress({ current: i + 1, total: fileArray.length })

            try {
                const title = file.name.replace(/\.(json|html?)$/i, '')
                const res = await sourcesApi.uploadFile(currentWorkspace.id, title, file)
                newSources.push(res.data)
                totalMessages += res.data.message_count
                successCount++
            } catch (err: any) {
                addNotification('error', `Ошибка загрузки ${file.name}: ${err.response?.data?.detail || 'Неизвестная ошибка'}`)
            }
        }

        // Update sources list
        setSources([...newSources, ...sources])

        if (successCount > 0) {
            addNotification('success', `Загружено ${successCount} файлов (${totalMessages} сообщений)`)

            // Reload workspace to update counts
            const wsRes = await workspacesApi.get(currentWorkspace.id)
            setCurrentWorkspace(wsRes.data)
        }

        setUploading(false)
        setUploadProgress({ current: 0, total: 0 })
        if (fileInputRef.current) {
            fileInputRef.current.value = ''
        }
    }

    const classifySource = async (sourceId: number) => {
        setClassifying(sourceId)
        try {
            const res = await sourcesApi.classify(sourceId)
            addNotification('success', `Найдено ${res.data.leads_created} лидов!`)

            // Reload workspace to update lead count
            if (currentWorkspace) {
                const wsRes = await workspacesApi.get(currentWorkspace.id)
                setCurrentWorkspace(wsRes.data)
            }
        } catch (err) {
            addNotification('error', 'Ошибка классификации')
        } finally {
            setClassifying(null)
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
        <div className="space-y-8 animate-fadeIn">
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
                                    <input
                                        ref={fileInputRef}
                                        type="file"
                                        accept=".json,.html"
                                        multiple
                                        onChange={handleFileUpload}
                                        className="hidden"
                                    />
                                    <button
                                        onClick={() => fileInputRef.current?.click()}
                                        disabled={uploading}
                                        className="btn-primary flex items-center gap-2"
                                    >
                                        {uploading ? (
                                            <>
                                                <Loader className="w-5 h-5 animate-spin" />
                                                {uploadProgress.total > 1 && (
                                                    <span>{uploadProgress.current}/{uploadProgress.total}</span>
                                                )}
                                            </>
                                        ) : (
                                            <Upload className="w-5 h-5" />
                                        )}
                                        Загрузить экспорт
                                    </button>
                                </div>
                            </div>

                            {/* Upload Instructions */}
                            <div className="bg-blue-50 rounded-xl p-4 mb-6">
                                <h3 className="font-medium text-blue-800 mb-2">📥 Как загрузить экспорт Telegram</h3>
                                <ol className="text-sm text-blue-700 space-y-1">
                                    <li>1. Откройте Telegram Desktop → Настройки → Продвинутые</li>
                                    <li>2. Нажмите "Экспорт данных Telegram"</li>
                                    <li>3. Выберите нужные чаты и формат JSON</li>
                                    <li>4. Загрузите полученный result.json сюда</li>
                                </ol>
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
                                                    ) : source.type === 'link' ? (
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
                                                    </div>
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <button
                                                    onClick={() => classifySource(source.id)}
                                                    disabled={classifying === source.id}
                                                    className="btn-ghost flex items-center gap-1 text-primary-600"
                                                >
                                                    {classifying === source.id ? (
                                                        <Loader className="w-4 h-4 animate-spin" />
                                                    ) : (
                                                        <CheckCircle className="w-4 h-4" />
                                                    )}
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

            {/* Create Modal */}
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
        </div>
    )
}
