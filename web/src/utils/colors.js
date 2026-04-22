/**
 * utils/colors.js — 全局配色常量
 *
 * 主题：Midnight Amber 量化终端
 *   深冷黑底 (#080b0f) + 琥珀金 accent (#e8a838) + 冷白文字
 *
 * 配色原则（A股习惯，红涨绿跌）：
 *   BUY  = 买入信号 = 红色系
 *   SELL = 卖出信号 = 绿色系
 */

export const C = {
  // ── 字体 ──
  fontData: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
  fontUI:   "'Syne', -apple-system, BlinkMacSystemFont, sans-serif",

  // ── 买入信号（红色系） ──
  buy:           '#e05252',          // 买入主色（暗红）
  buyBg:         '#2a1212',          // 买入背景
  buyBgLight:    'rgba(224,82,82,0.10)',
  buyText:       '#f08080',          // 买入文字（浅红）
  buyBorder:     '#c04040',

  // ── 卖出信号（绿色系） ──
  sell:          '#3a9e6e',          // 卖出主色（深青绿）
  sellBg:        '#0d2a1e',          // 卖出背景
  sellBgLight:   'rgba(58,158,110,0.10)',
  sellText:      '#5dbf95',          // 卖出文字（浅绿）
  sellBorder:    '#2e8055',

  // ── 中性 ──
  neutral:       '#6b7280',
  neutralBg:     '#111418',
  neutralBorder: '#2a2f38',
  neutralText:   '#8892a0',

  // ── 超买/超卖区域背景（遵循红涨绿跌）──
  overbought:       'rgba(58,158,110,0.08)',
  overboughtLine:   '#3a9e6e44',
  oversold:         'rgba(224,82,82,0.08)',
  oversoldLine:     '#e0525244',

  // ── K线颜色 ──
  candleUp:      '#e05252',          // 阳线红
  candleDown:    '#3a9e6e',          // 阴线绿

  // ── MA 均线 ──
  ma5:           '#e8a838',          // 琥珀金（accent）
  ma20:          '#5b9bd5',          // 钢蓝
  ma60:          '#c084fc',          // 淡紫

  // ── BOLL 轨道 ──
  bollUpper:     '#e05252',
  bollMid:       '#4a5568',
  bollLower:     '#3a9e6e',

  // ── MACD ──
  dif:           '#5b9bd5',          // 蓝
  dea:           '#e8a838',          // 琥珀
  macdBarPos:    '#e0525266',
  macdBarNeg:    '#3a9e6e66',

  // ── KDJ ──
  kLine:         '#5b9bd5',
  dLine:         '#e8a838',
  jLine:         '#c084fc',

  // ── 图表 UI ──
  chartBg:       '#080b0f',
  panelBg:       '#0e1117',
  border:        '#1c2230',
  border2:       '#252d3a',
  text:          '#d4d8de',
  textMuted:     '#8892a0',
  textDim:       '#3e4655',
  gridLine:      '#141920',
  axisLine:      '#1c2230',

  // ── Accent（琥珀金） ──
  accent:        '#e8a838',
  accentBg:      'rgba(232,168,56,0.10)',
  accentText:    '#f0c060',

  // ── 免责声明 ──
  disclaimer:    '#6b7280',
}
