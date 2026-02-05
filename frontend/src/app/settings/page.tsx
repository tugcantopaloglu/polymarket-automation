'use client'

import { useState, useEffect } from 'react'
import { Save, RefreshCw, AlertTriangle } from 'lucide-react'

interface Settings {
  trading: {
    minProfitMargin: number
    maxPositionUsd: number
    maxDailyLossUsd: number
    minLiquidityUsd: number
    kellyFraction: number
    stopLossPct: number
    takeProfitPct: number
  }
  alerts: {
    priceChangeThreshold: number
    volumeSpikeThreshold: number
    telegramEnabled: boolean
    discordEnabled: boolean
  }
  rateLimit: {
    requestsPerSecond: number
    burstLimit: number
  }
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  useEffect(() => {
    fetchSettings()
  }, [])

  const fetchSettings = async () => {
    try {
      const response = await fetch('/api/settings')
      const data = await response.json()
      setSettings(data)
    } catch (e) {
      setMessage({ type: 'error', text: 'Failed to load settings' })
    } finally {
      setIsLoading(false)
    }
  }

  const saveSettings = async () => {
    if (!settings) return
    
    setIsSaving(true)
    setMessage(null)

    try {
      const response = await fetch('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      })

      if (!response.ok) throw new Error('Save failed')
      
      setMessage({ type: 'success', text: 'Settings saved successfully' })
    } catch (e) {
      setMessage({ type: 'error', text: 'Failed to save settings' })
    } finally {
      setIsSaving(false)
    }
  }

  const updateTradingSetting = (key: keyof Settings['trading'], value: number) => {
    if (!settings) return
    setSettings({
      ...settings,
      trading: { ...settings.trading, [key]: value }
    })
  }

  const updateAlertSetting = (key: keyof Settings['alerts'], value: number | boolean) => {
    if (!settings) return
    setSettings({
      ...settings,
      alerts: { ...settings.alerts, [key]: value }
    })
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-polymarket-primary" />
      </div>
    )
  }

  if (!settings) {
    return <div className="card text-red-400">Failed to load settings</div>
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <header className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Settings</h1>
          <p className="text-gray-400">Configure bot parameters</p>
        </div>
        <div className="flex gap-4">
          <button
            onClick={fetchSettings}
            className="px-4 py-2 border border-polymarket-border rounded-lg flex items-center gap-2 hover:bg-white/5"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
          <button
            onClick={saveSettings}
            disabled={isSaving}
            className="px-4 py-2 bg-polymarket-primary text-black font-semibold rounded-lg flex items-center gap-2 hover:bg-polymarket-primary/90 disabled:opacity-50"
          >
            <Save className="w-4 h-4" />
            {isSaving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </header>

      {message && (
        <div className={`p-4 rounded-lg ${
          message.type === 'success' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
        }`}>
          {message.text}
        </div>
      )}

      <div className="card">
        <h3 className="text-lg font-semibold mb-4">Trading Parameters</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm text-gray-400 mb-2">Min Profit Margin (%)</label>
            <input
              type="number"
              value={settings.trading.minProfitMargin * 100}
              onChange={(e) => updateTradingSetting('minProfitMargin', Number(e.target.value) / 100)}
              className="w-full bg-polymarket-dark border border-polymarket-border rounded-lg p-3 text-white"
              step={0.1}
            />
            <p className="text-xs text-gray-500 mt-1">Minimum margin for arbitrage trades</p>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-2">Max Position ($)</label>
            <input
              type="number"
              value={settings.trading.maxPositionUsd}
              onChange={(e) => updateTradingSetting('maxPositionUsd', Number(e.target.value))}
              className="w-full bg-polymarket-dark border border-polymarket-border rounded-lg p-3 text-white"
            />
            <p className="text-xs text-gray-500 mt-1">Maximum single position size</p>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-2">Max Daily Loss ($)</label>
            <input
              type="number"
              value={settings.trading.maxDailyLossUsd}
              onChange={(e) => updateTradingSetting('maxDailyLossUsd', Number(e.target.value))}
              className="w-full bg-polymarket-dark border border-polymarket-border rounded-lg p-3 text-white"
            />
            <p className="text-xs text-gray-500 mt-1">Stop trading after this loss</p>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-2">Min Liquidity ($)</label>
            <input
              type="number"
              value={settings.trading.minLiquidityUsd}
              onChange={(e) => updateTradingSetting('minLiquidityUsd', Number(e.target.value))}
              className="w-full bg-polymarket-dark border border-polymarket-border rounded-lg p-3 text-white"
            />
            <p className="text-xs text-gray-500 mt-1">Minimum market liquidity to trade</p>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-2">Kelly Fraction</label>
            <input
              type="number"
              value={settings.trading.kellyFraction}
              onChange={(e) => updateTradingSetting('kellyFraction', Number(e.target.value))}
              className="w-full bg-polymarket-dark border border-polymarket-border rounded-lg p-3 text-white"
              step={0.05}
              min={0.1}
              max={1}
            />
            <p className="text-xs text-gray-500 mt-1">Fraction of Kelly criterion (0.25 = quarter Kelly)</p>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-2">Stop Loss (%)</label>
            <input
              type="number"
              value={settings.trading.stopLossPct * 100}
              onChange={(e) => updateTradingSetting('stopLossPct', Number(e.target.value) / 100)}
              className="w-full bg-polymarket-dark border border-polymarket-border rounded-lg p-3 text-white"
            />
            <p className="text-xs text-gray-500 mt-1">Exit position on this % loss</p>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-2">Take Profit (%)</label>
            <input
              type="number"
              value={settings.trading.takeProfitPct * 100}
              onChange={(e) => updateTradingSetting('takeProfitPct', Number(e.target.value) / 100)}
              className="w-full bg-polymarket-dark border border-polymarket-border rounded-lg p-3 text-white"
            />
            <p className="text-xs text-gray-500 mt-1">Exit position on this % profit</p>
          </div>
        </div>
      </div>

      <div className="card">
        <h3 className="text-lg font-semibold mb-4">Alert Settings</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm text-gray-400 mb-2">Price Change Threshold (%)</label>
            <input
              type="number"
              value={settings.alerts.priceChangeThreshold * 100}
              onChange={(e) => updateAlertSetting('priceChangeThreshold', Number(e.target.value) / 100)}
              className="w-full bg-polymarket-dark border border-polymarket-border rounded-lg p-3 text-white"
            />
            <p className="text-xs text-gray-500 mt-1">Alert on price moves exceeding this %</p>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-2">Volume Spike Threshold (x)</label>
            <input
              type="number"
              value={settings.alerts.volumeSpikeThreshold}
              onChange={(e) => updateAlertSetting('volumeSpikeThreshold', Number(e.target.value))}
              className="w-full bg-polymarket-dark border border-polymarket-border rounded-lg p-3 text-white"
              step={0.5}
            />
            <p className="text-xs text-gray-500 mt-1">Alert when volume exceeds average by this factor</p>
          </div>

          <div className="flex items-center justify-between p-3 bg-polymarket-dark rounded-lg">
            <div>
              <div className="font-medium">Telegram Notifications</div>
              <div className="text-sm text-gray-400">
                {settings.alerts.telegramEnabled ? 'Enabled' : 'Not configured'}
              </div>
            </div>
            <div className={`w-3 h-3 rounded-full ${settings.alerts.telegramEnabled ? 'bg-green-400' : 'bg-gray-500'}`} />
          </div>

          <div className="flex items-center justify-between p-3 bg-polymarket-dark rounded-lg">
            <div>
              <div className="font-medium">Discord Notifications</div>
              <div className="text-sm text-gray-400">
                {settings.alerts.discordEnabled ? 'Enabled' : 'Not configured'}
              </div>
            </div>
            <div className={`w-3 h-3 rounded-full ${settings.alerts.discordEnabled ? 'bg-green-400' : 'bg-gray-500'}`} />
          </div>
        </div>
      </div>

      <div className="card bg-yellow-500/10 border-yellow-500/30">
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-yellow-400 mt-0.5" />
          <div>
            <div className="font-medium text-yellow-400">Important</div>
            <p className="text-sm text-gray-300">
              Changes to trading parameters take effect immediately. Use caution when modifying position sizes and risk limits.
              Consider testing changes in dry-run mode first.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
