import { create } from 'zustand'

interface Workspace {
    id: number
    name: string
    description?: string
    sources_count: number
    leads_count: number
}

interface AppState {
    // Current workspace
    currentWorkspace: Workspace | null
    setCurrentWorkspace: (workspace: Workspace | null) => void

    // Loading states
    isLoading: boolean
    setIsLoading: (loading: boolean) => void

    // Notifications
    notifications: Array<{ id: string; type: 'success' | 'error' | 'info'; message: string }>
    addNotification: (type: 'success' | 'error' | 'info', message: string) => void
    removeNotification: (id: string) => void

    // Gamification cache
    gamificationData: {
        level: number
        xp: number
        streak: number
        dailyProgress: { messages: number; target: number }
    } | null
    setGamificationData: (data: any) => void
}

export const useStore = create<AppState>((set) => ({
    currentWorkspace: null,
    setCurrentWorkspace: (workspace) => set({ currentWorkspace: workspace }),

    isLoading: false,
    setIsLoading: (loading) => set({ isLoading: loading }),

    notifications: [],
    addNotification: (type, message) => {
        const id = Date.now().toString()
        set((state) => ({
            notifications: [...state.notifications, { id, type, message }],
        }))
        // Auto remove after 5 seconds
        setTimeout(() => {
            set((state) => ({
                notifications: state.notifications.filter((n) => n.id !== id),
            }))
        }, 5000)
    },
    removeNotification: (id) =>
        set((state) => ({
            notifications: state.notifications.filter((n) => n.id !== id),
        })),

    gamificationData: null,
    setGamificationData: (data) => set({ gamificationData: data }),
}))
