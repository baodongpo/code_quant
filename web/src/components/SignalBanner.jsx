/**
 * components/SignalBanner.jsx — 综合信号横幅
 *
 * Midnight Amber 主题：无 emoji，方角卡片，等宽数值
 *
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
    bg:         C.buyBg,
    border:     C.buyBorder,
    icon:       '▲',
    iconColor:  C.buy,
    titleColor: C.buyText,
    tag:        'BULLISH',
  },
  bearish: {
    bg:         C.sellBg,
    border:     C.sellBorder,
    icon:       '▼',
    iconColor:  C.sell,
    titleColor: C.sellText,
    tag:        'BEARISH',
  },
  neutral: {
    bg:         C.panelBg,
    border:     C.neutralBorder,
    icon:       '—',
    iconColor:  C.neutralText,
    titleColor: C.neutralText,
    tag:        'NEUTRAL',
  },
}

export default function SignalBanner({ level = 'neutral', score = 0, label = '', votes = [] }) {
  const cfg = LEVEL_CONFIG[level] || LEVEL_CONFIG.neutral

  // 进度条：-12~+12 映射到 0%~100%，0分居中
  const pct = Math.round(((score + 12) / 24) * 100)
  const barColor = level === 'bullish' ? C.buy : level === 'bearish' ? C.sell : C.neutralBorder

  return (
    <div style={{
      margin:       '10px 20px 0',
      padding:      '10px 16px',
      borderRadius: 3,
      border:       `1px solid ${cfg.border}`,
      borderLeft:   `3px solid ${cfg.border}`,
      background:   cfg.bg,
      display:      'flex',
      flexDirection: 'column',
      gap:          8,
    }}>
      {/* 主体区域 */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        {/* 左：信号 + 标题 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          {/* 大图标 */}
          <span style={{
            fontSize:   22,
            fontFamily: C.fontData,
            fontWeight: 700,
            color:      cfg.iconColor,
            lineHeight: 1,
            minWidth:   20,
            textAlign:  'center',
          }}>{cfg.icon}</span>

          <div>
            {/* 标题行 */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <span style={{
                fontSize:      11,
                fontFamily:    C.fontData,
                fontWeight:    700,
                letterSpacing: '0.12em',
                color:         cfg.iconColor,
                padding:       '1px 5px',
                border:        `1px solid ${cfg.border}`,
                borderRadius:  2,
              }}>{cfg.tag}</span>
              <span style={{
                fontSize:   14,
                fontWeight: 600,
                color:      cfg.titleColor,
              }}>
                {label}
              </span>
            </div>

            {/* 综合得分 + 进度条 */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 11, color: C.textMuted, letterSpacing: '0.04em' }}>SCORE</span>
              <span style={{
                fontSize:   13,
                fontFamily: C.fontData,
                fontWeight: 700,
                color:      cfg.titleColor,
                minWidth:   28,
              }}>
                {score > 0 ? `+${score}` : score}
              </span>
              {/* 进度条 */}
              <div style={{
                width:    110,
                height:   3,
                background: C.border,
                position: 'relative',
                overflow: 'hidden',
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
                  background: barColor,
                  left:       score >= 0 ? '50%' : `${pct}%`,
                  width:      `${Math.abs(score / 24 * 100)}%`,
                }} />
              </div>
            </div>
          </div>
        </div>

        {/* 右：各指标 chip */}
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
          {votes.map((v, i) => {
            const chipStyle = v.score > 0
              ? { bg: C.buyBg,      border: C.buyBorder,     text: C.buyText  }
              : v.score < 0
              ? { bg: C.sellBg,     border: C.sellBorder,    text: C.sellText }
              : { bg: C.neutralBg,  border: C.neutralBorder, text: C.neutralText }
            return (
              <span key={i} style={{
                display:      'inline-flex',
                alignItems:   'center',
                padding:      '2px 8px',
                borderRadius: 2,
                fontSize:     10,
                fontFamily:   C.fontData,
                letterSpacing: '0.03em',
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
        fontSize:   10,
        fontFamily: C.fontUI,
        color:      C.textDim,
        borderTop:  `1px solid ${C.border}`,
        paddingTop: 6,
        lineHeight: 1.5,
        letterSpacing: '0.02em',
      }}>
        以上为技术指标机械算法判断，仅用于辅助观察市场技术形态，不构成任何形式的投资建议。投资决策须用户独立判断，风险自负。
      </div>
    </div>
  )
}
