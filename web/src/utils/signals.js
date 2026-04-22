/**
 * utils/signals.js — 信号判断辅助（前端展示用）
 *
 * v3.5 更新：
 *  - 配色遵循红涨绿跌（买=红/卖=绿）
 *  - 文案通俗化（展示具体数值，初学者友好）
 *
 * 配色统一引用 utils/colors.js（Midnight Amber 主题），
 * 禁止硬编码 hex，以便主题切换时一处修改全局生效。
 */
import { C } from './colors.js'

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
    bullish: '▲ 超卖·下轨突破',
    bearish: '▼ 超买·上轨突破',
    neutral: '— 轨道内运行',
  },
  MACD: {
    bullish: '▲ MACD 金叉，上升动能增强',
    bearish: '▼ MACD 死叉，下行压力增大',
    neutral: '— MACD 持平',
  },
  RSI: {
    bullish: '▲ RSI 超卖，关注反弹机会',
    bearish: '▼ RSI 超买，短期或有回调',
    neutral: '— RSI 中性，暂无明显信号',
  },
  KDJ: {
    bullish: '▲ KDJ 金叉（低位），超卖反弹信号',
    bearish: '▼ KDJ 死叉（高位），超买回调信号',
    neutral: '— KDJ 中性',
  },
  MA: {
    bullish: '▲ MA 多头排列',
    bearish: '▼ MA 空头排列',
    neutral: '— 均线纠缠',
  },
  MAVOL: {
    volume_high: '↑ 放量',
    volume_low:  '↓ 缩量',
    neutral:     '— 正常量能',
  },
  composite: {
    bullish: '▲ 偏多',
    bearish: '▼ 偏空',
    neutral: '— 中性',
  },
}

/**
 * 信号对应的颜色（红涨绿跌：买=红/卖=绿）
 * bullish = 买入信号 = 红色系
 * bearish = 卖出信号 = 绿色系
 */
export const SIGNAL_COLORS = {
  bullish:     { bg: C.buyBg,      border: C.buyBorder,     text: C.buyText,     badge: C.buyBorder     },
  bearish:     { bg: C.sellBg,     border: C.sellBorder,    text: C.sellText,    badge: C.sellBorder    },
  neutral:     { bg: C.neutralBg,  border: C.neutralBorder, text: C.neutralText, badge: C.neutralBorder },
  volume_high: { bg: C.accentBg,   border: C.accent,        text: C.accentText,  badge: C.accent        },
  volume_low:  { bg: C.neutralBg,  border: C.neutralBorder, text: C.neutralText, badge: C.neutralBorder },
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
