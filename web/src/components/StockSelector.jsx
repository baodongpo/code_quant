/**
 * components/StockSelector.jsx — 股票下拉选择
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
  return '#8b949e'  // 中性灰
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
  // signals: { [stock_code]: 'bullish'|'bearish'|'neutral' }，可选
  const sigMap = signals || {}

  // 找当前选中股票用于着色顶部选择框文字
  const selected = stocks.find(s => s.stock_code === value)
  const selectedSignal = selected ? (sigMap[value] || 'neutral') : 'neutral'

  // 构建双层扁平化 optgroup 列表：先按市场，组内再按信号细分
  // 结构：[{ groupLabel, signal, stocks }]，空组跳过
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
      <span style={styles.label}>股票</span>
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
