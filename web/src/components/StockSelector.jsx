/**
 * components/StockSelector.jsx — 股票下拉选择
 * 显示格式：股票名称 (代码)，多头信号用红色、空头信号用绿色
 */
import React from 'react'

const styles = {
  label:  { fontSize: 13, color: '#8b949e', marginRight: 6 },
  select: {
    background: '#1c2128', border: '1px solid #30363d',
    padding: '4px 8px', borderRadius: 6, fontSize: 13, cursor: 'pointer',
    minWidth: 200,
  },
}

/** 根据信号判断文字颜色：bullish=红，bearish=绿，neutral=默认 */
function signalColor(signal) {
  if (signal === 'bullish') return '#ef5350'  // 红涨
  if (signal === 'bearish') return '#26a69a'  // 绿跌
  return '#e6edf3'
}

/** 格式化显示标签：名称+代码 */
function stockLabel(s) {
  return s.name ? `${s.name} (${s.stock_code})` : s.stock_code
}

/** 按市场分组，顺序：A股 → 港股 → 美股 */
const MARKET_GROUPS = [
  { key: 'A',  label: 'A股' },
  { key: 'HK', label: '港股' },
  { key: 'US', label: '美股' },
]

export default function StockSelector({ stocks, value, onChange, signals }) {
  // signals: { [stock_code]: 'bullish'|'bearish'|'neutral' }，可选
  const sigMap = signals || {}

  // 找当前选中股票用于着色顶部选择框文字
  const selected = stocks.find(s => s.stock_code === value)
  const selectedSignal = selected ? (sigMap[value] || 'neutral') : 'neutral'

  // 按市场分组，组内保留信号颜色
  const groups = MARKET_GROUPS.map(g => ({
    ...g,
    stocks: stocks.filter(s => s.market === g.key),
  })).filter(g => g.stocks.length > 0)

  return (
    <div style={{ display: 'flex', alignItems: 'center' }}>
      <span style={styles.label}>股票</span>
      <div style={{ position: 'relative' }}>
        <select
          style={{ ...styles.select, color: signalColor(selectedSignal) }}
          value={value || ''}
          onChange={e => onChange(e.target.value)}
        >
          {groups.map(g => (
            <optgroup key={g.key} label={g.label} style={{ color: '#8b949e' }}>
              {g.stocks.map(s => {
                const sig = sigMap[s.stock_code] || 'neutral'
                return (
                  <option
                    key={s.stock_code}
                    value={s.stock_code}
                    // NOTE: option style.color 在 Safari/Firefox 中不生效，属已知平台限制；
                    // 已选中项的颜色通过 <select> 自身的 color 属性正常显示（跨浏览器有效）
                    style={{ color: signalColor(sig), background: '#1c2128' }}
                  >
                    {stockLabel(s)}
                  </option>
                )
              })}
            </optgroup>
          ))}
        </select>
      </div>
    </div>
  )
}
