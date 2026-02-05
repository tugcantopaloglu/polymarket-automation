'use client'

import { TrendingUp, TrendingDown, DollarSign, Percent, Activity, Target } from 'lucide-react'

interface PortfolioData {
  totalValue: number
  unrealizedPnl: number
  realizedPnlToday: number
  winRate: number
  exposure: number
  maxDrawdown: number
  sharpeRatio: number
  numPositions: number
}

interface Props {
  portfolio?: PortfolioData
}

export function PortfolioOverview({ portfolio }: Props) {
  const stats = [
    {
      label: 'Portfolio Value',
      value: `$${(portfolio?.totalValue ?? 0).toFixed(2)}`,
      icon: DollarSign,
      change: null
    },
    {
      label: 'Unrealized P&L',
      value: `$${(portfolio?.unrealizedPnl ?? 0).toFixed(2)}`,
      icon: portfolio?.unrealizedPnl >= 0 ? TrendingUp : TrendingDown,
      change: portfolio?.unrealizedPnl ?? 0,
      isProfit: (portfolio?.unrealizedPnl ?? 0) >= 0
    },
    {
      label: 'Today\'s P&L',
      value: `$${(portfolio?.realizedPnlToday ?? 0).toFixed(2)}`,
      icon: Activity,
      change: portfolio?.realizedPnlToday ?? 0,
      isProfit: (portfolio?.realizedPnlToday ?? 0) >= 0
    },
    {
      label: 'Win Rate',
      value: `${((portfolio?.winRate ?? 0) * 100).toFixed(0)}%`,
      icon: Target,
      change: null
    },
    {
      label: 'Exposure',
      value: `${((portfolio?.exposure ?? 0) * 100).toFixed(0)}%`,
      icon: Percent,
      change: null
    },
    {
      label: 'Sharpe Ratio',
      value: (portfolio?.sharpeRatio ?? 0).toFixed(2),
      icon: Activity,
      change: null
    },
  ]

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
      {stats.map((stat) => (
        <div key={stat.label} className="stat-card">
          <div className="flex items-center gap-2 text-gray-400 text-sm mb-2">
            <stat.icon className="w-4 h-4" />
            {stat.label}
          </div>
          <div className={`text-2xl font-bold ${
            stat.change !== null 
              ? stat.isProfit ? 'text-green-400' : 'text-red-400'
              : ''
          }`}>
            {stat.value}
          </div>
        </div>
      ))}
    </div>
  )
}
