/**
 * utils/signals.js — 信号判断辅助（前端展示用）
 */

/** 信号枚举值（与后端 SignalEnum 一致） */
export const SIGNALS = {
  BULLISH:     'bullish',
  BEARISH:     'bearish',
  NEUTRAL:     'neutral',
  VOLUME_HIGH: 'volume_high',
  VOLUME_LOW:  'volume_low',
}

/** 各指标信号的文字标签（对照 PRD §4.2） */
export const SIGNAL_LABELS = {
  BOLL: {
    bullish: '🟢 超卖·下轨突破',
    bearish: '🔴 超买·上轨突破',
    neutral: '⚖️ 轨道内',
  },
  MACD: {
    bullish: '🟢 金叉·多头信号',
    bearish: '🔴 死叉·空头信号',
    neutral: '⚖️ 持平',
  },
  RSI: {
    bullish: '🟢 超卖区间·关注反弹',
    bearish: '🔴 超买区间·注意回调',
    neutral: '⚖️ 中性区间',
  },
  KDJ: {
    bullish: '🟢 金叉·超卖买入',
    bearish: '🔴 死叉·超买卖出',
    neutral: '⚖️ 中性',
  },
  MA: {
    bullish: '🟢 多头排列',
    bearish: '🔴 空头排列',
    neutral: '⚖️ 均线纠缠',
  },
  MAVOL: {
    volume_high: '🔊 放量',
    volume_low:  '🔇 缩量',
    neutral:     '── 正常量能',
  },
  composite: {
    bullish: '🟢 偏多',
    bearish: '🔴 偏空',
    neutral: '⚖️ 中性',
  },
}

/** 信号对应的颜色 */
export const SIGNAL_COLORS = {
  bullish:     { bg: '#1a3a2a', border: '#2ea043', text: '#3fb950', badge: '#2ea043' },
  bearish:     { bg: '#3a1a1a', border: '#f85149', text: '#ff7b72', badge: '#f85149' },
  neutral:     { bg: '#1c2128', border: '#484f58', text: '#8b949e', badge: '#484f58' },
  volume_high: { bg: '#3a2e1a', border: '#d29922', text: '#e3b341', badge: '#d29922' },
  volume_low:  { bg: '#1c2128', border: '#484f58', text: '#8b949e', badge: '#484f58' },
}

/** 获取某个指标的信号标签文字 */
export function getSignalLabel(indicator, signal) {
  const map = SIGNAL_LABELS[indicator] || {}
  return map[signal] || signal
}

/** 获取信号颜色配置 */
export function getSignalColor(signal) {
  return SIGNAL_COLORS[signal] || SIGNAL_COLORS.neutral
}
