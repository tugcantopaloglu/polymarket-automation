'use client'

import { PortfolioOverview } from '@/components/PortfolioOverview'
import { PerformanceChart } from '@/components/PerformanceChart'
import { RecentTrades } from '@/components/RecentTrades'
import { StrategyMetrics } from '@/components/StrategyMetrics'
import { MarketOpportunities } from '@/components/MarketOpportunities'
import { AlertsPanel } from '@/components/AlertsPanel'
import { useDashboard } from '@/hooks/useDashboard'

export default function Dashboard() {
  const { data, isLoading, error } = useDashboard()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-polymarket-primary" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="card text-red-400 text-center py-8">
        Failed to load dashboard data. Is the bot running?
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <header className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Dashboard</h1>
          <p className="text-gray-400">Polymarket Trading Bot</p>
        </div>
        <div className="flex items-center gap-4">
          <span className={`px-3 py-1 rounded-full text-sm ${
            data?.status === 'running' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
          }`}>
            {data?.status === 'running' ? '● Running' : '○ Stopped'}
          </span>
          <span className="text-gray-400 text-sm">
            Last updated: {new Date().toLocaleTimeString()}
          </span>
        </div>
      </header>

      <PortfolioOverview portfolio={data?.portfolio} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PerformanceChart data={data?.performance} />
        <StrategyMetrics strategies={data?.strategies} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <RecentTrades trades={data?.trades} />
        </div>
        <div>
          <AlertsPanel alerts={data?.alerts} />
        </div>
      </div>

      <MarketOpportunities opportunities={data?.opportunities} />
    </div>
  )
}
