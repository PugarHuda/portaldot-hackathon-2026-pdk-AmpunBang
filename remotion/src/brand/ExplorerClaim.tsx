import React from 'react';
import {AbsoluteFill} from 'remotion';
import {loadFont} from '@remotion/google-fonts/Inter';
import {loadFont as loadMono} from '@remotion/google-fonts/JetBrainsMono';
import {Wordmark} from './Logo';

loadFont();
loadMono();

const BG = '#0a0c10';
const INK = '#ededed';
const MUTED = '#7d8590';
const ACCENT = '#3fb950';
const RULE = 'rgba(237,237,237,0.08)';

const STEPS: Array<[string, string]> = [
  ['1', 'Follow @PortaldotDevKit'],
  ['2', 'Quote Retweet this post + tag 3 friends'],
  ['3', 'Join our Discord'],
  ['4', 'Fill the form → get your Dev Explorer role'],
];

export const ExplorerClaim: React.FC = () => {
  return (
    <AbsoluteFill style={{backgroundColor: BG, overflow: 'hidden'}}>
      <div
        style={{
          position: 'absolute',
          inset: 0,
          padding: '96px 110px',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
        }}
      >
        <div style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between'}}>
          <Wordmark size={{font: 96, dot: 28, dotOffsetY: 6}} dotColor={ACCENT} />
          <div
            style={{
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: 26,
              fontWeight: 600,
              color: ACCENT,
              letterSpacing: '0.14em',
              textTransform: 'uppercase',
              border: `1px solid ${ACCENT}`,
              borderRadius: 8,
              padding: '10px 20px',
            }}
          >
            How To Claim
          </div>
        </div>

        <div>
          <div
            style={{
              fontFamily: 'Inter, sans-serif',
              fontWeight: 600,
              fontSize: 60,
              color: INK,
              lineHeight: 1.15,
              letterSpacing: '-0.01em',
              marginBottom: 48,
            }}
          >
            How to claim your Dev Explorer role.
          </div>

          <div style={{display: 'flex', flexDirection: 'column', gap: 26}}>
            {STEPS.map(([n, label]) => (
              <div key={n} style={{display: 'flex', alignItems: 'center', gap: 26}}>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: 48,
                    height: 48,
                    borderRadius: '50%',
                    border: `1px solid ${ACCENT}`,
                    fontFamily: 'JetBrains Mono, monospace',
                    fontWeight: 700,
                    fontSize: 22,
                    color: ACCENT,
                    flexShrink: 0,
                  }}
                >
                  {n}
                </div>
                <div
                  style={{
                    fontFamily: 'JetBrains Mono, monospace',
                    fontSize: 28,
                    color: INK,
                  }}
                >
                  {label}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <div style={{height: 1, background: RULE, marginBottom: 32}} />
          <div style={{display: 'flex', alignItems: 'baseline', justifyContent: 'space-between'}}>
            <div
              style={{
                fontFamily: 'Inter, sans-serif',
                fontWeight: 600,
                fontSize: 28,
                color: INK,
              }}
            >
              Build better on Portaldot.
            </div>
            <div
              style={{
                fontFamily: 'JetBrains Mono, monospace',
                fontSize: 20,
                color: MUTED,
              }}
            >
              forms.gle/x4dN8E6XinAe4tnQ6
            </div>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
