import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Leads from './pages/Leads'
import Drafts from './pages/Drafts'
import Campaigns from './pages/Campaigns'
import Templates from './pages/Templates'
import Analytics from './pages/Analytics'

import InSequence from './pages/InSequence'

function App() {
    return (
        <Routes>
            <Route path="/" element={<Layout />}>
                <Route index element={<Navigate to="/dashboard" replace />} />
                <Route path="dashboard" element={<Dashboard />} />
                <Route path="leads" element={<Leads />} />
                <Route path="drafts" element={<Drafts />} />
                <Route path="campaigns" element={<Campaigns />} />
                <Route path="in-sequence" element={<InSequence />} />
                <Route path="templates" element={<Templates />} />
                <Route path="analytics" element={<Analytics />} />
            </Route>
        </Routes>
    )
}

export default App
