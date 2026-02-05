'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { 
  LayoutDashboard, 
  TrendingUp, 
  History, 
  Settings, 
  Bell, 
  BarChart3, 
  Wallet,
  BookOpen,
  AlertTriangle
} from 'lucide-react'

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Portfolio', href: '/portfolio', icon: Wallet },
  { name: 'Markets', href: '/markets', icon: TrendingUp },
  { name: 'Trades', href: '/trades', icon: History },
  { name: 'Strategies', href: '/strategies', icon: BarChart3 },
  { name: 'Alerts', href: '/alerts', icon: Bell },
  { name: 'Backtest', href: '/backtest', icon: BookOpen },
  { name: 'Settings', href: '/settings', icon: Settings },
]

export function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="fixed left-0 top-0 h-full w-64 bg-polymarket-card border-r border-polymarket-border">
      <div className="p-6 border-b border-polymarket-border">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-polymarket-primary/20 flex items-center justify-center">
            <TrendingUp className="w-6 h-6 text-polymarket-primary" />
          </div>
          <div>
            <h2 className="font-bold">Polymarket Bot</h2>
            <span className="text-xs text-gray-400">v2.0.0</span>
          </div>
        </div>
      </div>

      <nav className="p-4 space-y-1">
        {navigation.map((item) => {
          const isActive = pathname === item.href
          return (
            <Link
              key={item.name}
              href={item.href}
              className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                isActive
                  ? 'bg-polymarket-primary/20 text-polymarket-primary'
                  : 'text-gray-400 hover:text-white hover:bg-white/5'
              }`}
            >
              <item.icon className="w-5 h-5" />
              {item.name}
            </Link>
          )
        })}
      </nav>

      <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-polymarket-border">
        <div className="card bg-yellow-500/10 border-yellow-500/30">
          <div className="flex items-center gap-2 text-yellow-400 text-sm">
            <AlertTriangle className="w-4 h-4" />
            <span>Trading involves risk</span>
          </div>
        </div>
      </div>
    </aside>
  )
}
