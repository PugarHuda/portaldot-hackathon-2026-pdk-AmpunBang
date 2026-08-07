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
const BLURPLE = '#5865f2';
const ZEALY_YELLOW = '#fbc42a';
const RULE = 'rgba(237,237,237,0.08)';

const CHIPS: Array<[string, string, string]> = [
  ['Discord', 'support · bug reports · updates', BLURPLE],
  ['Zealy', 'quests live now', ZEALY_YELLOW],
];

export const CommunityCard: React.FC = () => {
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
        <Wordmark size={{font: 96, dot: 28, dotOffsetY: 6}} dotColor={ACCENT} />

        <div>
          <div
            style={{
              fontFamily: 'Inter, sans-serif',
              fontWeight: 600,
              fontSize: 64,
              color: INK,
              lineHeight: 1.15,
              letterSpacing: '-0.01em',
              maxWidth: 1080,
              marginBottom: 28,
            }}
          >
            PDK now has an official Discord, and Zealy quests are live.
          </div>
          <div
            style={{
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: 24,
              color: MUTED,
              lineHeight: 1.5,
              maxWidth: 980,
            }}
          >
            Come report bugs, ask questions, and earn points while you help the project.
          </div>
        </div>

        <div>
          <div style={{height: 1, background: RULE, marginBottom: 36}} />
          <div style={{display: 'flex', gap: 28}}>
            {CHIPS.map(([name, sub, color]) => (
              <div
                key={name}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 6,
                  padding: '20px 32px',
                  border: `1px solid ${color}`,
                  borderRadius: 12,
                  minWidth: 320,
                }}
              >
                <div
                  style={{
                    fontFamily: 'JetBrains Mono, monospace',
                    fontWeight: 700,
                    fontSize: 32,
                    color,
                  }}
                >
                  {name}
                </div>
                <div
                  style={{
                    fontFamily: 'Inter, sans-serif',
                    fontSize: 18,
                    color: MUTED,
                  }}
                >
                  {sub}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
