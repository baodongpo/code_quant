/**
 * utils/signals.js — 信号判断辅助（前端展示用）
 *
 * v3.5 更新：
 *  - 配色遵循红涨绿跌（买=红/卖=绿）
 *  - 文案通俗化（展示具体数值，初学者友好）
 */

/** 信号枚举值（与后端 SignalEnum 一致） */
export const SIGNALS = {
  BULLISH:     'bullish',
  BEARISH:     'bearish',
  NEUTRAL:     'neutral',
  VOLUME_HIGH: 'volume_high',
  VOLUME_LOW:  'volume_low',
}

/** 各指标信号的文字标签（通俗化，遵循红买绿卖） */
export const SIGNAL_LABELS = {
  BOLL: {
    bullish: '🔴 超卖·下轨突破',
    bearish: '🟢 超买·上轨突破',
    neutral: '⚖️ 轨道内运行',
  },
  MACD: {
    bullish: '🔴 MACD 金叉，上升动能增强',
    bearish: '🟢 MACD 死叉，下行压力增大',
    neutral: '⚖️ MACD 持平',
  },
  RSI: {
    bullish: '🔴 RSI 超卖，关注反弹机会',
    bearish: '🟢 RSI 超买，短期或有回调',
    neutral: '⚖️ RSI 中性，暂无明显信号',
  },
  KDJ: {
    bullish: '🔴 KDJ 金叉（低位），超卖反弹信号',
    bearish: '🟢 KDJ 死叉（高位），超买回调信号',
    neutral: '⚖️ KDJ 中性',
  },
  MA: {
    bullish: '🔴 MA 多头排列',
    bearish: '🟢 MA 空头排列',
    neutral: '⚖️ 均线纠缠',
  },
  MAVOL: {
    volume_high: '🔊 放量',
    volume_low:  '🔇 缩量',
    neutral:     '── 正常量能',
  },
  composite: {
    bullish: '🔴 偏多',
    bearish: '🟢 偏空',
    neutral: '⚖️ 中性',
  },
}

/**
 * 信号对应的颜色（红涨绿跌：买=红/卖=绿）
 * bullish = 买入信号 = 红色系
 * bearish = 卖出信号 = 绿色系
 */
export const SIGNAL_COLORS = {
  bullish:     { bg: '#3a1a1a', border: '#f85149', text: '#ff7b72', badge: '#f85149' },
  bearish:     { bg: '#1a3a2a', border: '#2ea043', text: '#3fb950', badge: '#2ea043' },
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
