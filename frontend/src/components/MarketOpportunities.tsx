'use client'

import { TrendingUp, Clock, DollarSign } from 'lucide-react'

interface Opportunity {
  id: string
  market: string
  strategy: string
  confidence: number
  expectedProfit: number
  margin?: number
  daysToResolution?: number
}

interface Props {
  opportunities?: Opportunity[]
}

const mockOpportunities: Opportunity[] = [
  { id: '1', market: 'Will inflation drop below 3%?', strategy: 'arbitrage', confidence: 0.85, expectedProfit: 12.50, margin: 0.052 },
  { id: '2', market: 'SpaceX Mars mission in 2025?', strategy: 'bonding', confidence: 0.92, expectedProfit: 8.20, daysToResolution: 5 },
  { id: '3', market: 'Apple Vision Pro sales exceed 1M?', strategy: 'momentum', confidence: 0.68, expectedProfit: 15.30 },
  { id: '4', market: 'Next Fed chair announcement?', strategy: 'value', confidence: 0.75, expectedProfit: 6.80 },
]

const strategyColors: Record<string, string> = {
  arbitrage: 'bg-green-500/20 text-green-400',
  bonding: 'bg-blue-500/20 text-blue-400',
  momentum: 'bg-purple-500/20 text-purple-400',
  value: 'bg-orange-500/20 text-orange-400',
  whale: 'bg-cyan-500/20 text-cyan-400',
}

export function MarketOpportunities({ opportunities = mockOpportunities }: Props) {
  return (
    <div className="card">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold">Active Opportunities</h3>
        <a href="/markets" className="text-polymarket-primary text-sm hover:underline">Browse markets</a>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {opportunities.map((opp) => (
          <div key={opp.id} className="p-4 bg-polymarket-dark rounded-lg hover:bg-polymarket-dark/80 transition-colors cursor-pointer">
            <div className="flex items-center gap-2 mb-2">
              <span className={`px-2 py-0.5 rounded text-xs ${strategyColors[opp.strategy]}`}>
                {opp.strategy}
              </span>
              <span className="text-xs text-gray-400">{(opp.confidence * 100).toFixed(0)}% conf</span>
            </div>
            
            <div className="text-sm font-medium mb-3 line-clamp-2">{opp.market}</div>
            
            <div className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-1 text-green-400">
                <DollarSign className="w-4 h-4" />
                <span>${opp.expectedProfit.toFixed(2)}</span>
              </div>
              {opp.margin && (
                <div className="text-gray-400">
                  {(opp.margin * 100).toFixed(1)}% margin
                </div>
              )}
              {opp.daysToResolution && (
                <div className="flex items-center gap-1 text-gray-400">
                  <Clock className="w-4 h-4" />
                  <span>{opp.daysToResolution}d</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
