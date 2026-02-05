'use client'

import { format } from 'date-fns'
import { Bell, TrendingUp, AlertTriangle, DollarSign, Zap } from 'lucide-react'

interface Alert {
  id: string
  type: 'arbitrage' | 'price_change' | 'volume_spike' | 'risk' | 'trade'
  title: string
  message: string
  severity: 'info' | 'warning' | 'success' | 'error'
  timestamp: string
}

interface Props {
  alerts?: Alert[]
}

const iconMap = {
  arbitrage: DollarSign,
  price_change: TrendingUp,
  volume_spike: Zap,
  risk: AlertTriangle,
  trade: Bell,
}

const colorMap = {
  info: 'text-blue-400 bg-blue-400/10',
  warning: 'text-yellow-400 bg-yellow-400/10',
  success: 'text-green-400 bg-green-400/10',
  error: 'text-red-400 bg-red-400/10',
}

const mockAlerts: Alert[] = [
  { id: '1', type: 'arbitrage', title: 'Arbitrage Found', message: '5.2% margin on BTC market', severity: 'success', timestamp: new Date().toISOString() },
  { id: '2', type: 'price_change', title: 'Price Alert', message: 'ETH market moved 8%', severity: 'info', timestamp: new Date(Date.now() - 1800000).toISOString() },
  { id: '3', type: 'risk', title: 'Daily Limit', message: '80% of daily loss limit reached', severity: 'warning', timestamp: new Date(Date.now() - 3600000).toISOString() },
  { id: '4', type: 'trade', title: 'Trade Executed', message: 'Bought YES on Fed market', severity: 'success', timestamp: new Date(Date.now() - 7200000).toISOString() },
]

export function AlertsPanel({ alerts = mockAlerts }: Props) {
  return (
    <div className="card">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold">Alerts</h3>
        <a href="/alerts" className="text-polymarket-primary text-sm hover:underline">Configure</a>
      </div>
      
      <div className="space-y-3">
        {alerts.map((alert) => {
          const Icon = iconMap[alert.type]
          return (
            <div key={alert.id} className={`p-3 rounded-lg ${colorMap[alert.severity]}`}>
              <div className="flex items-start gap-3">
                <Icon className="w-5 h-5 mt-0.5" />
                <div className="flex-1">
                  <div className="font-medium text-sm">{alert.title}</div>
                  <div className="text-xs opacity-80">{alert.message}</div>
                  <div className="text-xs opacity-60 mt-1">
                    {format(new Date(alert.timestamp), 'HH:mm')}
                  </div>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
