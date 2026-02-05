import useSWR from 'swr'

const fetcher = (url: string) => fetch(url).then(res => res.json())

interface DashboardData {
  status: 'running' | 'stopped'
  portfolio: {
    totalValue: number
    unrealizedPnl: number
    realizedPnlToday: number
    winRate: number
    exposure: number
    maxDrawdown: number
    sharpeRatio: number
    numPositions: number
  }
  performance: Array<{
    date: string
    value: number
    pnl: number
  }>
  strategies: Array<{
    name: string
    trades: number
    winRate: number
    pnl: number
    opportunities: number
  }>
  trades: Array<{
    id: string
    market: string
    side: 'BUY' | 'SELL'
    outcome: 'YES' | 'NO'
    size: number
    price: number
    pnl?: number
    strategy: string
    timestamp: string
  }>
  alerts: Array<{
    id: string
    type: string
    title: string
    message: string
    severity: string
    timestamp: string
  }>
  opportunities: Array<{
    id: string
    market: string
    strategy: string
    confidence: number
    expectedProfit: number
    margin?: number
    daysToResolution?: number
  }>
}

export function useDashboard() {
  const { data, error, isLoading, mutate } = useSWR<DashboardData>(
    '/api/dashboard',
    fetcher,
    {
      refreshInterval: 30000,
      revalidateOnFocus: true,
      errorRetryCount: 3,
    }
  )

  return {
    data,
    error,
    isLoading,
    refresh: mutate,
  }
}

export function usePortfolio() {
  return useSWR('/api/portfolio', fetcher, { refreshInterval: 10000 })
}

export function useTrades(limit = 50) {
  return useSWR(`/api/trades?limit=${limit}`, fetcher, { refreshInterval: 30000 })
}

export function useMarkets() {
  return useSWR('/api/markets', fetcher, { refreshInterval: 60000 })
}

export function useAlerts() {
  return useSWR('/api/alerts', fetcher, { refreshInterval: 10000 })
}

export function useBacktest() {
  return {
    runBacktest: async (params: {
      strategy: string
      startDate: string
      endDate: string
      initialCapital: number
    }) => {
      const response = await fetch('/api/backtest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      })
      return response.json()
    }
  }
}
