import { useEffect, useState } from 'react'
import { Plus, Edit2, Trash2, Copy, Check } from 'lucide-react'
import { useStore } from '../store/useStore'
import { templatesApi } from '../lib/api'

interface Template {
    id: number
    name: string
    category?: string
    text: string
    usage_count: number
    success_rate?: number
}

const CATEGORIES = [
    { value: 'Bots_TG_WA_VK', label: '🤖 Боты' },
    { value: 'Landing_Sites', label: '🌐 Сайты' },
    { value: 'Parsing_Analytics_Reports', label: '📊 Парсинг' },
    { value: 'Integrations_Sheets_CRM_n8n', label: '🔗 Интеграции' },
    { value: 'Sales_CRM_Process', label: '💼 CRM' },
    { value: 'General', label: '📝 Общие' },
]

export default function Templates() {
    const { addNotification } = useStore()
    const [templates, setTemplates] = useState<Template[]>([])
    const [loading, setLoading] = useState(true)
    const [showModal, setShowModal] = useState(false)
    const [editingTemplate, setEditingTemplate] = useState<Template | null>(null)
    const [formData, setFormData] = useState({ name: '', category: '', text: '' })
    const [copiedId, setCopiedId] = useState<number | null>(null)

    useEffect(() => {
        loadTemplates()
    }, [])

    const loadTemplates = async () => {
        try {
            const res = await templatesApi.list()
            setTemplates(res.data)
        } catch (err) {
            console.error('Failed to load templates:', err)
        } finally {
            setLoading(false)
        }
    }

    const seedDefaults = async () => {
        try {
            await templatesApi.seedDefaults()
            addNotification('success', 'Шаблоны по умолчанию добавлены')
            loadTemplates()
        } catch (err) {
            addNotification('error', 'Ошибка')
        }
    }

    const handleSubmit = async () => {
        if (!formData.name.trim() || !formData.text.trim()) {
            addNotification('error', 'Заполните название и текст')
            return
        }

        try {
            if (editingTemplate) {
                await templatesApi.update(editingTemplate.id, formData)
                addNotification('success', 'Шаблон обновлен')
            } else {
                await templatesApi.create(formData)
                addNotification('success', 'Шаблон создан')
            }
            loadTemplates()
            closeModal()
        } catch (err) {
            addNotification('error', 'Ошибка сохранения')
        }
    }

    const deleteTemplate = async (id: number) => {
        if (!confirm('Удалить шаблон?')) return

        try {
            await templatesApi.delete(id)
            setTemplates(templates.filter(t => t.id !== id))
            addNotification('success', 'Шаблон удален')
        } catch (err) {
            addNotification('error', 'Ошибка удаления')
        }
    }

    const openEditModal = (template: Template) => {
        setEditingTemplate(template)
        setFormData({
            name: template.name,
            category: template.category || '',
            text: template.text,
        })
        setShowModal(true)
    }

    const closeModal = () => {
        setShowModal(false)
        setEditingTemplate(null)
        setFormData({ name: '', category: '', text: '' })
    }

    const copyTemplate = (template: Template) => {
        navigator.clipboard.writeText(template.text)
        setCopiedId(template.id)
        setTimeout(() => setCopiedId(null), 2000)
        addNotification('success', 'Скопировано!')
    }

    return (
        <div className="space-y-6 animate-fadeIn">
            {/* Header */}
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold text-white flex items-center gap-3">
                        🧠 Шаблоны сообщений
                    </h1>
                    <p className="text-white/70 mt-1">
                        Готовые тексты для быстрого ответа
                    </p>
                </div>
                <div className="flex gap-3">
                    {templates.length === 0 && (
                        <button onClick={seedDefaults} className="btn-secondary">
                            Добавить примеры
                        </button>
                    )}
                    <button
                        onClick={() => setShowModal(true)}
                        className="btn-primary flex items-center gap-2"
                    >
                        <Plus className="w-5 h-5" />
                        Новый шаблон
                    </button>
                </div>
            </div>

            {/* Templates Grid */}
            {loading ? (
                <div className="flex items-center justify-center h-64">
                    <div className="animate-spin rounded-full h-12 w-12 border-4 border-white border-t-transparent"></div>
                </div>
            ) : templates.length === 0 ? (
                <div className="card text-center py-12">
                    <h3 className="text-xl font-bold text-gray-700 mb-2">Нет шаблонов</h3>
                    <p className="text-gray-500 mb-4">Создайте первый шаблон или добавьте примеры</p>
                </div>
            ) : (
                <div className="grid grid-cols-2 gap-6">
                    {templates.map((template) => (
                        <div key={template.id} className="card">
                            <div className="flex items-start justify-between mb-3">
                                <div>
                                    <h3 className="font-bold text-gray-800">{template.name}</h3>
                                    {template.category && (
                                        <span className="text-sm text-gray-500">
                                            {CATEGORIES.find(c => c.value === template.category)?.label || template.category}
                                        </span>
                                    )}
                                </div>
                                <div className="flex items-center gap-1">
                                    <button
                                        onClick={() => copyTemplate(template)}
                                        className="p-2 hover:bg-gray-100 rounded-lg text-gray-400 hover:text-gray-600"
                                    >
                                        {copiedId === template.id ? (
                                            <Check className="w-4 h-4 text-green-500" />
                                        ) : (
                                            <Copy className="w-4 h-4" />
                                        )}
                                    </button>
                                    <button
                                        onClick={() => openEditModal(template)}
                                        className="p-2 hover:bg-gray-100 rounded-lg text-gray-400 hover:text-gray-600"
                                    >
                                        <Edit2 className="w-4 h-4" />
                                    </button>
                                    <button
                                        onClick={() => deleteTemplate(template.id)}
                                        className="p-2 hover:bg-red-100 rounded-lg text-gray-400 hover:text-red-500"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                </div>
                            </div>

                            <p className="text-gray-600 text-sm line-clamp-4 mb-3 whitespace-pre-wrap">
                                {template.text}
                            </p>

                            <div className="flex items-center gap-4 text-xs text-gray-400">
                                <span>Использован: {template.usage_count} раз</span>
                                {template.success_rate && (
                                    <span>Ответили: {Math.round(template.success_rate * 100)}%</span>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Modal */}
            {showModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <div className="bg-white rounded-2xl p-6 w-[600px] max-h-[90vh] overflow-auto animate-fadeIn">
                        <h2 className="text-xl font-bold text-gray-800 mb-4">
                            {editingTemplate ? 'Редактировать шаблон' : 'Новый шаблон'}
                        </h2>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Название
                                </label>
                                <input
                                    type="text"
                                    value={formData.name}
                                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                    placeholder="Например: Первый контакт - Бот"
                                    className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-500"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Категория
                                </label>
                                <select
                                    value={formData.category}
                                    onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                                    className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-500"
                                >
                                    <option value="">Без категории</option>
                                    {CATEGORIES.map((cat) => (
                                        <option key={cat.value} value={cat.value}>{cat.label}</option>
                                    ))}
                                </select>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Текст шаблона
                                </label>
                                <textarea
                                    value={formData.text}
                                    onChange={(e) => setFormData({ ...formData, text: e.target.value })}
                                    placeholder="Текст сообщения..."
                                    rows={6}
                                    className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-500 resize-none"
                                />
                                <p className="text-xs text-gray-400 mt-1">
                                    Используйте {'{{переменная}}'} для подстановки (например: {'{{project_type}}'})
                                </p>
                            </div>
                        </div>

                        <div className="flex gap-3 mt-6">
                            <button onClick={closeModal} className="flex-1 btn-ghost">
                                Отмена
                            </button>
                            <button onClick={handleSubmit} className="flex-1 btn-primary">
                                {editingTemplate ? 'Сохранить' : 'Создать'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
