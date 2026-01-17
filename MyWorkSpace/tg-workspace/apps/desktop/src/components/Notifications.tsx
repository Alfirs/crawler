import { X, CheckCircle, AlertCircle, Info } from 'lucide-react'
import { useStore } from '../store/useStore'

export default function Notifications() {
    const { notifications, removeNotification } = useStore()

    if (notifications.length === 0) return null

    return (
        <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
            {notifications.map((notification) => (
                <div
                    key={notification.id}
                    className={`flex items-center gap-3 px-4 py-3 rounded-xl shadow-lg animate-slideIn ${notification.type === 'success' ? 'bg-green-500 text-white' :
                            notification.type === 'error' ? 'bg-red-500 text-white' :
                                'bg-blue-500 text-white'
                        }`}
                >
                    {notification.type === 'success' && <CheckCircle className="w-5 h-5" />}
                    {notification.type === 'error' && <AlertCircle className="w-5 h-5" />}
                    {notification.type === 'info' && <Info className="w-5 h-5" />}
                    <span className="font-medium">{notification.message}</span>
                    <button
                        onClick={() => removeNotification(notification.id)}
                        className="ml-2 hover:bg-white/20 rounded p-1"
                    >
                        <X className="w-4 h-4" />
                    </button>
                </div>
            ))}
        </div>
    )
}
