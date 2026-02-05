'use client'

import { useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts'
import { Play, TrendingUp, TrendingDown, Target, BarChart2 } from 'lucide-react'

interface BacktestResult {
  strategy: string
  startDate: string
  endDate: string
  initialCapital: number
  finalCapital: number
  totalReturn: number
  totalTrades: number
  winningTrades: number
  losingTrades: number
  winRate: number
  profitFactor: number
  maxDrawdown: number
  sharpeRatio: number
  sortinoRatio: number
  avgTradePnl: number
  avgWinner: number
  avgLoser: number
  largestWinner: number
  largestLoser: number
  avgHoldingPeriod: number
  equityCurve: Array<{ date: string; value: number; pnl: number }>
  trades: Array<{
    timestamp: string
    market: string
    side: string
    outcome: string
    size: number
    entryPrice: number
    exitPrice: number | null
    pnl: number
  }>
}

const strategies = [
  { id: 'arbitrage', name: 'Arbitrage', description: 'Exploits Yes + No < 1.0 opportunities' },
  { id: 'bonding', name: 'Bonding', description: 'High probability near resolution' },
  { id: 'momentum', name: 'Momentum', description: 'Follows price trends' },
  { id: 'value', name: 'Value', description: 'Kelly criterion-based positioning' },
]

export default function BacktestPage() {
  const [strategy, setStrategy] = useState('arbitrage')
  const [startDate, setStartDate] = useState(() => {
    const d = new Date()
    d.setMonth(d.getMonth() - 1)
    return d.toISOString().split('T')[0]
  })
  const [endDate, setEndDate] = useState(() => new Date().toISOString().split('T')[0])
  const [initialCapital, setInitialCapital] = useState(1000)
  const [isRunning, setIsRunning] = useState(false)
  const [result, setResult] = useState<BacktestResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const runBacktest = async () => {
    setIsRunning(true)
    setError(null)

    try {
      const response = await fetch('/api/backtest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ strategy, startDate, endDate, initialCapital }),
      })

      if (!response.ok) {
        throw new Error('Backtest failed')
      }

      const data = await response.json()
      setResult(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setIsRunning(false)
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-3xl font-bold">Backtesting</h1>
        <p className="text-gray-400">Test strategies against historical data</p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="card">
          <h3 className="text-lg font-semibold mb-4">Configuration</h3>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-2">Strategy</label>
              <select
                value={strategy}
                onChange={(e) => setStrategy(e.target.value)}
                className="w-full bg-polymarket-dark border border-polymarket-border rounded-lg p-3 text-white"
              >
                {strategies.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
              <p className="text-xs text-gray-500 mt-1">
                {strategies.find(s => s.id === strategy)?.description}
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-400 mb-2">Start Date</label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full bg-polymarket-dark border border-polymarket-border rounded-lg p-3 text-white"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-2">End Date</label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="w-full bg-polymarket-dark border border-polymarket-border rounded-lg p-3 text-white"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-2">Initial Capital ($)</label>
              <input
                type="number"
                value={initialCapital}
                onChange={(e) => setInitialCapital(Number(e.target.value))}
                className="w-full bg-polymarket-dark border border-polymarket-border rounded-lg p-3 text-white"
                min={100}
                max={100000}
              />
            </div>

            <button
              onClick={runBacktest}
              disabled={isRunning}
              className="w-full bg-polymarket-primary text-black font-semibold py-3 rounded-lg flex items-center justify-center gap-2 hover:bg-polymarket-primary/90 disabled:opacity-50"
            >
              {isRunning ? (
                <>
                  <div className="animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-black" />
                  Running...
                </>
              ) : (
                <>
                  <Play className="w-5 h-5" />
                  Run Backtest
                </>
              )}
            </button>

            {error && (
              <div className="text-red-400 text-sm bg-red-500/10 p-3 rounded-lg">
                {error}
              </div>
            )}
          </div>
        </div>

        <div className="lg:col-span-2">
          {result ? (
            <div className="space-y-6">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="stat-card">
                  <div className="text-sm text-gray-400">Final Value</div>
                  <div className="text-2xl font-bold">${result.finalCapital.toFixed(2)}</div>
                </div>
                <div className="stat-card">
                  <div className="text-sm text-gray-400">Total Return</div>
                  <div className={`text-2xl font-bold ${result.totalReturn >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {(result.totalReturn * 100).toFixed(1)}%
                  </div>
                </div>
                <div className="stat-card">
                  <div className="text-sm text-gray-400">Win Rate</div>
                  <div className="text-2xl font-bold">{(result.winRate * 100).toFixed(0)}%</div>
                </div>
                <div className="stat-card">
                  <div className="text-sm text-gray-400">Sharpe Ratio</div>
                  <div className="text-2xl font-bold">{result.sharpeRatio.toFixed(2)}</div>
                </div>
              </div>

              <div className="card">
                <h4 className="text-lg font-semibold mb-4">Equity Curve</h4>
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={result.equityCurve}>
                      <defs>
                        <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#00D395" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#00D395" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#30363D" />
                      <XAxis dataKey="date" stroke="#6B7280" tick={{ fontSize: 10 }} />
                      <YAxis stroke="#6B7280" tickFormatter={(v) => `$${v}`} />
                      <Tooltip 
                        contentStyle={{ backgroundColor: '#161B22', border: '1px solid #30363D' }}
                      />
                      <Area type="monotone" dataKey="value" stroke="#00D395" fill="url(#colorEquity)" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                <div className="card">
                  <div className="flex items-center gap-2 text-gray-400 mb-2">
                    <BarChart2 className="w-4 h-4" />
                    <span>Total Trades</span>
                  </div>
                  <div className="text-xl font-bold">{result.totalTrades}</div>
                  <div className="text-sm text-gray-500">
                    {result.winningTrades}W / {result.losingTrades}L
                  </div>
                </div>
                <div className="card">
                  <div className="flex items-center gap-2 text-gray-400 mb-2">
                    <TrendingDown className="w-4 h-4" />
                    <span>Max Drawdown</span>
                  </div>
                  <div className="text-xl font-bold text-red-400">
                    {(result.maxDrawdown * 100).toFixed(1)}%
                  </div>
                </div>
                <div className="card">
                  <div className="flex items-center gap-2 text-gray-400 mb-2">
                    <Target className="w-4 h-4" />
                    <span>Profit Factor</span>
                  </div>
                  <div className="text-xl font-bold">{result.profitFactor.toFixed(2)}</div>
                </div>
                <div className="card">
                  <div className="text-gray-400 text-sm">Avg Winner</div>
                  <div className="text-lg font-bold text-green-400">${result.avgWinner.toFixed(2)}</div>
                </div>
                <div className="card">
                  <div className="text-gray-400 text-sm">Avg Loser</div>
                  <div className="text-lg font-bold text-red-400">${Math.abs(result.avgLoser).toFixed(2)}</div>
                </div>
                <div className="card">
                  <div className="text-gray-400 text-sm">Sortino Ratio</div>
                  <div className="text-lg font-bold">{result.sortinoRatio.toFixed(2)}</div>
                </div>
              </div>
            </div>
          ) : (
            <div className="card flex items-center justify-center h-96 text-gray-400">
              Configure and run a backtest to see results
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
