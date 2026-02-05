'use client'

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, AreaChart } from 'recharts'

interface PerformanceData {
  date: string
  value: number
  pnl: number
}

interface Props {
  data?: PerformanceData[]
}

const mockData: PerformanceData[] = Array.from({ length: 30 }, (_, i) => ({
  date: new Date(Date.now() - (29 - i) * 24 * 60 * 60 * 1000).toLocaleDateString(),
  value: 1000 + Math.random() * 200 * i / 10 - 50,
  pnl: Math.random() * 20 - 5
}))

export function PerformanceChart({ data = mockData }: Props) {
  return (
    <div className="card">
      <h3 className="text-lg font-semibold mb-4">Portfolio Performance</h3>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#00D395" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#00D395" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#30363D" />
            <XAxis 
              dataKey="date" 
              stroke="#6B7280" 
              tick={{ fontSize: 12 }}
              tickLine={false}
            />
            <YAxis 
              stroke="#6B7280" 
              tick={{ fontSize: 12 }}
              tickLine={false}
              tickFormatter={(value) => `$${value}`}
            />
            <Tooltip 
              contentStyle={{ 
                backgroundColor: '#161B22', 
                border: '1px solid #30363D',
                borderRadius: '8px'
              }}
              labelStyle={{ color: '#9CA3AF' }}
            />
            <Area 
              type="monotone" 
              dataKey="value" 
              stroke="#00D395" 
              fillOpacity={1} 
              fill="url(#colorValue)" 
              strokeWidth={2}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
