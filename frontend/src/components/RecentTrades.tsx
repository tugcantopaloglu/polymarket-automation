'use client'

import { format } from 'date-fns'
import { ArrowUpRight, ArrowDownRight } from 'lucide-react'

interface Trade {
  id: string
  market: string
  side: 'BUY' | 'SELL'
  outcome: 'YES' | 'NO'
  size: number
  price: number
  pnl?: number
  strategy: string
  timestamp: string
}

interface Props {
  trades?: Trade[]
}

const mockTrades: Trade[] = [
  { id: '1', market: 'Will BTC hit $100k by end of 2024?', side: 'BUY', outcome: 'YES', size: 25, price: 0.45, pnl: 5.20, strategy: 'momentum', timestamp: new Date().toISOString() },
  { id: '2', market: 'Fed rate cut in March?', side: 'SELL', outcome: 'NO', size: 15, price: 0.32, pnl: -2.10, strategy: 'arbitrage', timestamp: new Date(Date.now() - 3600000).toISOString() },
  { id: '3', market: 'SpaceX Starship success?', side: 'BUY', outcome: 'YES', size: 30, price: 0.78, pnl: 8.50, strategy: 'bonding', timestamp: new Date(Date.now() - 7200000).toISOString() },
  { id: '4', market: 'Trump wins primary?', side: 'BUY', outcome: 'YES', size: 20, price: 0.92, strategy: 'bonding', timestamp: new Date(Date.now() - 14400000).toISOString() },
  { id: '5', market: 'ETH merge successful?', side: 'SELL', outcome: 'YES', size: 10, price: 0.55, pnl: 3.20, strategy: 'value', timestamp: new Date(Date.now() - 28800000).toISOString() },
]

export function RecentTrades({ trades = mockTrades }: Props) {
  return (
    <div className="card">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold">Recent Trades</h3>
        <a href="/trades" className="text-polymarket-primary text-sm hover:underline">View all</a>
      </div>
      
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="text-gray-400 text-sm border-b border-polymarket-border">
              <th className="text-left py-3 font-medium">Market</th>
              <th className="text-left py-3 font-medium">Side</th>
              <th className="text-right py-3 font-medium">Size</th>
              <th className="text-right py-3 font-medium">Price</th>
              <th className="text-right py-3 font-medium">P&L</th>
              <th className="text-right py-3 font-medium">Time</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((trade) => (
              <tr key={trade.id} className="border-b border-polymarket-border/50 hover:bg-white/5">
                <td className="py-3">
                  <div className="max-w-xs truncate">{trade.market}</div>
                  <div className="text-xs text-gray-400">{trade.strategy}</div>
                </td>
                <td className="py-3">
                  <span className={`flex items-center gap-1 ${
                    trade.side === 'BUY' ? 'text-green-400' : 'text-red-400'
                  }`}>
                    {trade.side === 'BUY' ? <ArrowUpRight className="w-4 h-4" /> : <ArrowDownRight className="w-4 h-4" />}
                    {trade.side} {trade.outcome}
                  </span>
                </td>
                <td className="py-3 text-right">${trade.size.toFixed(2)}</td>
                <td className="py-3 text-right">{(trade.price * 100).toFixed(0)}¢</td>
                <td className={`py-3 text-right ${
                  trade.pnl !== undefined
                    ? trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'
                    : 'text-gray-400'
                }`}>
                  {trade.pnl !== undefined ? `$${trade.pnl.toFixed(2)}` : '—'}
                </td>
                <td className="py-3 text-right text-gray-400 text-sm">
                  {format(new Date(trade.timestamp), 'HH:mm')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
