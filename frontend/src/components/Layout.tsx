import { Outlet, NavLink } from 'react-router-dom'
import {
    LayoutDashboard,
    Users,
    FileEdit,
    Megaphone,
    FileText,
    BarChart3,
    Settings,
    Zap,
} from 'lucide-react'
import './Layout.css'

const navItems = [
    { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { to: '/leads', icon: Users, label: 'Leads' },
    { to: '/drafts', icon: FileEdit, label: 'Drafts' },
    { to: '/campaigns', icon: Megaphone, label: 'Campaigns' },
    { to: '/in-sequence', icon: Zap, label: 'In Sequence' },
    { to: '/templates', icon: FileText, label: 'Templates' },
    { to: '/analytics', icon: BarChart3, label: 'Analytics' },
]

export default function Layout() {
    return (
        <div className="layout">
            {/* Sidebar */}
            <aside className="sidebar">
                <div className="sidebar-header">
                    <div className="logo">
                        <span className="logo-text">Xendex AI</span>
                    </div>
                </div>

                <nav className="sidebar-nav">
                    {navItems.map((item) => (
                        <NavLink
                            key={item.to}
                            to={item.to}
                            className={({ isActive }) =>
                                `nav-item ${isActive ? 'nav-item-active' : ''}`
                            }
                        >
                            <item.icon className="nav-icon" />
                            <span>{item.label}</span>
                        </NavLink>
                    ))}
                </nav>

                <div className="sidebar-footer">
                    <button className="nav-item">
                        <Settings className="nav-icon" />
                        <span>Settings</span>
                    </button>
                </div>
            </aside>

            {/* Main Content */}
            <main className="main-content">
                <Outlet />
            </main>
        </div>
    )
}
