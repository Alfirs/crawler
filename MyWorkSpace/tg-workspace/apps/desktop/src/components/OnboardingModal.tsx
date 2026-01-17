import { useState, useEffect } from 'react'
import { X, Briefcase, Check } from 'lucide-react'
import { settingsApi } from '../lib/api'

interface Profession {
    code: string
    label: string
}

interface OnboardingModalProps {
    isOpen: boolean
    onComplete: (professions: string[]) => void
}

export default function OnboardingModal({ isOpen, onComplete }: OnboardingModalProps) {
    const [professions, setProfessions] = useState<Profession[]>([])
    const [selected, setSelected] = useState<string[]>([])
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)

    useEffect(() => {
        if (isOpen) {
            loadProfessions()
        }
    }, [isOpen])

    const loadProfessions = async () => {
        try {
            const res = await settingsApi.getProfessionsList()
            setProfessions(res.data)
        } catch (err) {
            console.error('Failed to load professions:', err)
        } finally {
            setLoading(false)
        }
    }

    const toggleProfession = (code: string) => {
        setSelected(prev =>
            prev.includes(code)
                ? prev.filter(p => p !== code)
                : [...prev, code]
        )
    }

    const handleSave = async () => {
        if (selected.length === 0) return

        setSaving(true)
        try {
            await settingsApi.setUserProfessions(selected)
            onComplete(selected)
        } catch (err) {
            console.error('Failed to save professions:', err)
        } finally {
            setSaving(false)
        }
    }

    if (!isOpen) return null

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl max-w-lg w-full max-h-[90vh] overflow-hidden">
                {/* Header */}
                <div className="bg-gradient-to-r from-indigo-500 to-purple-600 p-6 text-white">
                    <div className="flex items-center gap-3 mb-2">
                        <Briefcase className="w-8 h-8" />
                        <h2 className="text-2xl font-bold">Добро пожаловать!</h2>
                    </div>
                    <p className="text-indigo-100">
                        Выберите свою профессию, чтобы видеть только релевантные лиды
                    </p>
                </div>

                {/* Content */}
                <div className="p-6 overflow-y-auto max-h-[50vh]">
                    {loading ? (
                        <div className="flex items-center justify-center py-8">
                            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"></div>
                        </div>
                    ) : (
                        <div className="grid grid-cols-2 gap-3">
                            {professions.map(prof => (
                                <button
                                    key={prof.code}
                                    onClick={() => toggleProfession(prof.code)}
                                    className={`p-3 rounded-lg border-2 text-left transition-all ${selected.includes(prof.code)
                                            ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/30'
                                            : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                                        }`}
                                >
                                    <div className="flex items-center gap-2">
                                        {selected.includes(prof.code) && (
                                            <Check className="w-4 h-4 text-indigo-500" />
                                        )}
                                        <span className={`text-sm ${selected.includes(prof.code)
                                                ? 'text-indigo-700 dark:text-indigo-300 font-medium'
                                                : 'text-gray-700 dark:text-gray-300'
                                            }`}>
                                            {prof.label}
                                        </span>
                                    </div>
                                </button>
                            ))}
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="p-6 border-t dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
                    <button
                        onClick={handleSave}
                        disabled={selected.length === 0 || saving}
                        className={`w-full py-3 px-4 rounded-lg font-medium transition-all ${selected.length === 0
                                ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                                : 'bg-indigo-600 text-white hover:bg-indigo-700'
                            }`}
                    >
                        {saving ? (
                            <span className="flex items-center justify-center gap-2">
                                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                                Сохранение...
                            </span>
                        ) : (
                            `Продолжить${selected.length > 0 ? ` (${selected.length})` : ''}`
                        )}
                    </button>
                    <p className="text-center text-xs text-gray-500 mt-3">
                        Можно изменить позже в настройках
                    </p>
                </div>
            </div>
        </div>
    )
}
