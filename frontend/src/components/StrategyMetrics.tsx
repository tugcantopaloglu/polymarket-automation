'use client'

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'

interface StrategyData {
  name: string
  trades: number
  winRate: number
  pnl: number
  opportunities: number
}

interface Props {
  strategies?: StrategyData[]
}

const mockStrategies: StrategyData[] = [
  { name: 'Arbitrage', trades: 45, winRate: 0.92, pnl: 125.50, opportunities: 156 },
  { name: 'Bonding', trades: 23, winRate: 0.87, pnl: 67.20, opportunities: 89 },
  { name: 'Momentum', trades: 18, winRate: 0.61, pnl: -12.30, opportunities: 45 },
  { name: 'Value', trades: 12, winRate: 0.75, pnl: 34.80, opportunities: 28 },
]

export function StrategyMetrics({ strategies = mockStrategies }: Props) {
  return (
    <div className="card">
      <h3 className="text-lg font-semibold mb-4">Strategy Performance</h3>
      <div className="space-y-4">
        {strategies.map((strategy) => (
          <div key={strategy.name} className="flex items-center justify-between p-3 bg-polymarket-dark rounded-lg">
            <div className="flex-1">
              <div className="font-medium">{strategy.name}</div>
              <div className="text-sm text-gray-400">
                {strategy.trades} trades • {(strategy.winRate * 100).toFixed(0)}% win rate
              </div>
            </div>
            <div className={`text-right ${strategy.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              <div className="font-bold">${strategy.pnl.toFixed(2)}</div>
              <div className="text-xs text-gray-400">{strategy.opportunities} opportunities</div>
            </div>
          </div>
        ))}
      </div>
      
      <div className="mt-4 h-48">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={strategies} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" stroke="#30363D" />
            <XAxis type="number" stroke="#6B7280" tickFormatter={(v) => `$${v}`} />
            <YAxis dataKey="name" type="category" stroke="#6B7280" width={80} />
            <Tooltip 
              contentStyle={{ 
                backgroundColor: '#161B22', 
                border: '1px solid #30363D',
                borderRadius: '8px'
              }}
            />
            <Bar dataKey="pnl" radius={[0, 4, 4, 0]}>
              {strategies.map((entry, index) => (
                <Cell key={index} fill={entry.pnl >= 0 ? '#00D395' : '#EF4444'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
