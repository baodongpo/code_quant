/**
 * components/StockSelector.jsx — 股票下拉选择
 *
 * Midnight Amber 主题：深色 select、等宽字体
 *
 * 分组策略（双层扁平化）：
 *   外层：市场（A股 → 港股 → 美股）
 *   内层：信号（看多 → 中性 → 看空），空组跳过
 *
 * 由于 HTML <optgroup> 不支持嵌套，采用扁平化方案：
 *   <optgroup label="A股 · 看多">  ← 市场+信号联合标签
 *   <optgroup label="A股 · 中性">
 *   <optgroup label="港股 · 看多">
 *   ...以此类推，空 optgroup 直接跳过
 *
 * 当前选中项的颜色通过 <select> 自身 color 属性展示（跨浏览器有效）；
 * <option> 的 style.color 在 Safari/Firefox 中不生效，属已知平台限制。
 */
import React from 'react'
import { C } from '../utils/colors.js'

const styles = {
  label: {
    fontSize:      9,
    fontFamily:    C.fontUI,
    letterSpacing: '0.10em',
    textTransform: 'uppercase',
    color:         C.textDim,
    marginRight:   8,
  },
  select: {
    background:    C.panelBg,
    border:        `1px solid ${C.border2}`,
    padding:       '4px 8px',
    borderRadius:  2,
    fontSize:      12,
    fontFamily:    C.fontData,
    cursor:        'pointer',
    minWidth:      200,
    color:         C.text,
  },
}

/** 根据信号判断文字颜色 */
function signalColor(signal) {
  if (signal === 'bullish') return C.buyText
  if (signal === 'bearish') return C.sellText
  return C.textMuted
}

/** 格式化显示标签：名称+代码 */
function stockLabel(s) {
  return s.name ? `${s.name} (${s.stock_code})` : s.stock_code
}

/** 市场分组顺序 */
const MARKET_GROUPS = [
  { key: 'A',  label: 'A股' },
  { key: 'HK', label: '港股' },
  { key: 'US', label: '美股' },
]

/** 信号分组顺序（看多优先） */
const SIGNAL_GROUPS = [
  { key: 'bullish', label: '看多' },
  { key: 'neutral', label: '中性' },
  { key: 'bearish', label: '看空' },
]

export default function StockSelector({ stocks, value, onChange, signals }) {
  const sigMap = signals || {}

  const selected = stocks.find(s => s.stock_code === value)
  const selectedSignal = selected ? (sigMap[value] || 'neutral') : 'neutral'

  const flatGroups = []
  for (const market of MARKET_GROUPS) {
    const marketStocks = stocks.filter(s => s.market === market.key)
    if (marketStocks.length === 0) continue

    for (const sig of SIGNAL_GROUPS) {
      const groupStocks = marketStocks.filter(s => (sigMap[s.stock_code] || 'neutral') === sig.key)
      if (groupStocks.length === 0) continue
      flatGroups.push({
        groupLabel: `${market.label} · ${sig.label}`,
        signal: sig.key,
        stocks: groupStocks,
      })
    }
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center' }}>
      <span style={styles.label}>STOCK</span>
      <div style={{ position: 'relative' }}>
        <select
          style={{ ...styles.select, color: signalColor(selectedSignal) }}
          value={value || ''}
          onChange={e => onChange(e.target.value)}
        >
          {flatGroups.map(g => (
            <optgroup
              key={g.groupLabel}
              label={g.groupLabel}
              style={{ color: signalColor(g.signal) }}
            >
              {g.stocks.map(s => {
                const sig = sigMap[s.stock_code] || 'neutral'
                return (
                  <option
                    key={s.stock_code}
                    value={s.stock_code}
                    style={{ color: signalColor(sig), background: C.panelBg }}
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
