/**
 * components/SignalBanner.jsx — 综合信号横幅
 *
 * 位置：顶部导航栏与主图之间（页面顶部全宽卡片）
 * 严禁包含任何交易下单逻辑，所有信号均为技术指标机械判断，仅供辅助参考。
 *
 * Props:
 *   level  - 'bullish' | 'bearish' | 'neutral'
 *   score  - number (-12 ~ +12)
 *   label  - string 结论文案
 *   votes  - Array<{ indicator, score, label }>
 */
import React from 'react'
import { C } from '../utils/colors.js'

const LEVEL_CONFIG = {
  bullish: {
    bg:       '#2a0d0d',
    border:   C.buy,
    icon:     '🔴',
    titleColor: C.buyText,
  },
  bearish: {
    bg:       '#0d2316',
    border:   C.sell,
    icon:     '🟢',
    titleColor: C.sellText,
  },
  neutral: {
    bg:       C.panelBg,
    border:   C.neutralBorder,
    icon:     '⚖️',
    titleColor: C.neutralText,
  },
}

export default function SignalBanner({ level = 'neutral', score = 0, label = '', votes = [] }) {
  const cfg = LEVEL_CONFIG[level] || LEVEL_CONFIG.neutral

  // 进度条：-12~+12 映射到 0%~100%，0分居中
  const pct = Math.round(((score + 12) / 24) * 100)
  const barColor = level === 'bullish' ? C.buy : level === 'bearish' ? C.sell : '#fadb14'

  return (
    <div style={{
      margin:       '12px 20px 0',
      padding:      '12px 20px',
      borderRadius: 10,
      border:       `1px solid ${cfg.border}`,
      background:   cfg.bg,
      display:      'flex',
      flexDirection: 'column',
      gap:          8,
    }}>
      {/* 主体区域 */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        {/* 左：图标 + 标题 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 28, lineHeight: 1 }}>{cfg.icon}</span>
          <div>
            <div style={{
              fontSize:   16,
              fontWeight: 700,
              color:      cfg.titleColor,
              marginBottom: 4,
            }}>
              {label}
            </div>
            {/* 综合得分 + 进度条 */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 12, color: C.textMuted }}>综合得分</span>
              <span style={{ fontSize: 14, fontWeight: 700, color: cfg.titleColor }}>
                {score > 0 ? `+${score}` : score}
              </span>
              <div style={{
                width:        120,
                height:       6,
                borderRadius: 3,
                background:   C.border,
                position:     'relative',
                overflow:     'hidden',
              }}>
                {/* 中线 */}
                <div style={{
                  position:   'absolute',
                  left:       '50%',
                  top:        0,
                  width:      1,
                  height:     '100%',
                  background: C.border2,
                }} />
                {/* 填充 */}
                <div style={{
                  position:   'absolute',
                  top:        0,
                  height:     '100%',
                  borderRadius: 3,
                  background: barColor,
                  left:       score >= 0 ? '50%' : `${pct}%`,
                  width:      `${Math.abs(score / 24 * 100)}%`,
                }} />
              </div>
            </div>
          </div>
        </div>

        {/* 右：各指标 chip */}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          {votes.map((v, i) => {
            const chipStyle = v.score > 0
              ? { bg: '#3a1a1a', border: C.buy,     text: C.buyText  }
              : v.score < 0
              ? { bg: '#1a3a2a', border: C.sell,    text: C.sellText }
              : { bg: C.neutralBg, border: C.neutralBorder, text: C.neutralText }
            return (
              <span key={i} style={{
                display:      'inline-flex',
                alignItems:   'center',
                padding:      '4px 10px',
                borderRadius: 20,
                fontSize:     11,
                whiteSpace:   'nowrap',
                background:   chipStyle.bg,
                border:       `1px solid ${chipStyle.border}`,
                color:        chipStyle.text,
              }}>
                {v.label}
              </span>
            )
          })}
        </div>
      </div>

      {/* 免责声明（常驻，不可关闭） */}
      <div style={{
        fontSize:    10,
        color:       C.textDim,
        borderTop:   `1px solid ${C.border}`,
        paddingTop:  8,
        lineHeight:  1.6,
      }}>
        ⚠️ 以上为技术指标机械算法判断，仅用于辅助观察市场技术形态，不构成任何形式的投资建议。投资决策须用户独立判断，风险自负。
      </div>
    </div>
  )
}
