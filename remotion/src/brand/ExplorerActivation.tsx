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

const TASKS: Array<[string, string]> = [
  ['01', 'Test the CLI'],
  ['02', 'Report bugs'],
  ['03', 'Write docs'],
  ['04', 'Onboard devs'],
];

export const ExplorerActivation: React.FC = () => {
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
            Explorer Activation
          </div>
        </div>

        <div>
          <div
            style={{
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: 22,
              fontWeight: 600,
              color: ACCENT,
              letterSpacing: '0.04em',
              marginBottom: 18,
            }}
          >
            🏆 Grand Champion — Hackathon Season 1
          </div>
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
            Become a PDK Dev Explorer.
          </div>
          <div
            style={{
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: 24,
              color: MUTED,
              lineHeight: 1.5,
              maxWidth: 1000,
            }}
          >
            Test the CLI, break things, and help shape the dev tooling that turns cryptic
            Portaldot errors into clear, actionable fixes.
          </div>
        </div>

        <div>
          <div style={{height: 1, background: RULE, marginBottom: 36}} />
          <div style={{display: 'flex', gap: 20}}>
            {TASKS.map(([n, label]) => (
              <div
                key={label}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 10,
                  padding: '20px 24px',
                  border: `1px solid ${RULE}`,
                  borderRadius: 12,
                  flex: 1,
                }}
              >
                <div
                  style={{
                    fontFamily: 'JetBrains Mono, monospace',
                    fontWeight: 700,
                    fontSize: 22,
                    color: ACCENT,
                  }}
                >
                  {n}
                </div>
                <div
                  style={{
                    fontFamily: 'Inter, sans-serif',
                    fontSize: 20,
                    color: INK,
                  }}
                >
                  {label}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
