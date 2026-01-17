import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import Layout from './components/Layout'

// Lazy load all pages for better performance
const Dashboard = lazy(() => import('./pages/Dashboard'))
const LeadsInbox = lazy(() => import('./pages/LeadsInbox'))
const LeadDetail = lazy(() => import('./pages/LeadDetail'))
const Templates = lazy(() => import('./pages/Templates'))
const Reports = lazy(() => import('./pages/Reports'))
const Settings = lazy(() => import('./pages/Settings'))
const Workspaces = lazy(() => import('./pages/Workspaces'))
const TelegramChats = lazy(() => import('./pages/TelegramChats'))
const Autopost = lazy(() => import('./pages/Autopost'))

// Fast loading spinner
function PageLoader() {
    return (
        <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-10 w-10 border-3 border-white border-t-transparent"></div>
        </div>
    )
}

function App() {
    return (
        <BrowserRouter>
            <Routes>
                <Route path="/" element={<Layout />}>
                    <Route index element={
                        <Suspense fallback={<PageLoader />}><Dashboard /></Suspense>
                    } />
                    <Route path="workspaces" element={
                        <Suspense fallback={<PageLoader />}><Workspaces /></Suspense>
                    } />
                    <Route path="leads" element={
                        <Suspense fallback={<PageLoader />}><LeadsInbox /></Suspense>
                    } />
                    <Route path="leads/:leadId" element={
                        <Suspense fallback={<PageLoader />}><LeadDetail /></Suspense>
                    } />
                    <Route path="templates" element={
                        <Suspense fallback={<PageLoader />}><Templates /></Suspense>
                    } />
                    <Route path="reports" element={
                        <Suspense fallback={<PageLoader />}><Reports /></Suspense>
                    } />
                    <Route path="settings" element={
                        <Suspense fallback={<PageLoader />}><Settings /></Suspense>
                    } />
                    <Route path="telegram" element={
                        <Suspense fallback={<PageLoader />}><TelegramChats /></Suspense>
                    } />
                    <Route path="autopost" element={
                        <Suspense fallback={<PageLoader />}><Autopost /></Suspense>
                    } />
                </Route>
            </Routes>
        </BrowserRouter>
    )
}

export default App
