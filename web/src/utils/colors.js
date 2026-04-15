/**
 * utils/colors.js — 全局配色常量
 *
 * 配色原则（A股习惯，红涨绿跌）：
 *   BUY  = 买入信号 = 红色系
 *   SELL = 卖出信号 = 绿色系
 */

export const C = {
  // ── 买入信号（红色系） ──
  buy:           '#f85149',          // 买入主色（强红）
  buyBg:         '#3a1a1a',          // 买入背景
  buyBgLight:    'rgba(248,81,73,0.12)',
  buyText:       '#ff7b72',          // 买入文字（浅红）
  buyBorder:     '#f85149',

  // ── 卖出信号（绿色系） ──
  sell:          '#2ea043',          // 卖出主色（强绿）
  sellBg:        '#1a3a2a',          // 卖出背景
  sellBgLight:   'rgba(46,160,67,0.12)',
  sellText:      '#3fb950',          // 卖出文字（浅绿）
  sellBorder:    '#2ea043',

  // ── 中性 ──
  neutral:       '#8c8c8c',
  neutralBg:     '#1c2128',
  neutralBorder: '#484f58',
  neutralText:   '#8b949e',

  // ── 超买/超卖区域背景（遵循红涨绿跌）──
  // 超买 = 卖出信号 = 绿底
  overbought:       'rgba(46,160,67,0.10)',
  overboughtLine:   '#26a69a55',
  // 超卖 = 买入信号 = 红底
  oversold:         'rgba(248,81,73,0.10)',
  oversoldLine:     '#ef535055',

  // ── K线颜色 ──
  candleUp:      '#ef5350',          // 阳线红
  candleDown:    '#26a69a',          // 阴线绿

  // ── MA 均线 ──
  ma5:           '#f0c040',
  ma20:          '#388bfd',
  ma60:          '#ff9500',

  // ── BOLL 轨道 ──
  bollUpper:     '#f85149',
  bollMid:       '#8b949e',
  bollLower:     '#26a69a',

  // ── MACD ──
  dif:           '#79c0ff',
  dea:           '#f0c040',
  macdBarPos:    '#ef535088',
  macdBarNeg:    '#26a69a88',

  // ── KDJ ──
  kLine:         '#79c0ff',
  dLine:         '#f0c040',
  jLine:         '#bc8cff',

  // ── 图表 UI ──
  chartBg:       '#0d1117',
  panelBg:       '#161b22',
  border:        '#2d333b',
  border2:       '#30363d',
  text:          '#e6edf3',
  textMuted:     '#8b949e',
  textDim:       '#484f58',
  gridLine:      '#21262d',
  axisLine:      '#30363d',
  accent:        '#388bfd',
  accentBg:      'rgba(56,139,253,0.12)',
  accentText:    '#79c0ff',

  // ── 免责声明 ──
  disclaimer:    '#bfbfbf',
}
