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

const TOPICS = ['Hackathon win', 'Live bug story', 'Explorer Activation'];

// ponytail: date/time are props because they change every Space — override them
// in Remotion Studio or via `--props`, no code edit per event.
export type SpaceAnnounceProps = {
  date: string;
  time: string;
};

export const SpaceAnnounce: React.FC<SpaceAnnounceProps> = ({date, time}) => {
  return (
    <AbsoluteFill style={{backgroundColor: BG, overflow: 'hidden'}}>
      {/* ambient glow */}
      <div
        style={{
          position: 'absolute',
          top: -260,
          right: -220,
          width: 900,
          height: 900,
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(63,185,80,0.16) 0%, rgba(63,185,80,0) 68%)',
        }}
      />
      {/* faint dot grid texture */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          backgroundImage: 'radial-gradient(rgba(237,237,237,0.08) 1.5px, transparent 1.5px)',
          backgroundSize: '34px 34px',
          maskImage: 'linear-gradient(to bottom, black, transparent 78%)',
          WebkitMaskImage: 'linear-gradient(to bottom, black, transparent 78%)',
        }}
      />

      <div
        style={{
          position: 'absolute',
          inset: 0,
          padding: '90px 110px',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
        }}
      >
        <div style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between'}}>
          <Wordmark size={{font: 88, dot: 26, gap: 22, dotOffsetY: 6}} dotColor={ACCENT} />
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: 24,
              fontWeight: 600,
              color: ACCENT,
              letterSpacing: '0.14em',
              textTransform: 'uppercase',
              border: `1px solid ${ACCENT}`,
              borderRadius: 999,
              padding: '10px 24px',
            }}
          >
            <span
              style={{
                width: 9,
                height: 9,
                borderRadius: '50%',
                background: ACCENT,
                boxShadow: `0 0 12px 2px ${ACCENT}`,
              }}
            />
            Live X Space
          </div>
        </div>

        <div>
          <div
            style={{
              fontFamily: 'Inter, sans-serif',
              fontWeight: 800,
              fontSize: 80,
              color: INK,
              lineHeight: 1.04,
              letterSpacing: '-0.02em',
              maxWidth: 1150,
              marginBottom: 22,
            }}
          >
            PDK Explorer Kickoff
          </div>
          <div
            style={{
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: 27,
              color: MUTED,
              maxWidth: 980,
              marginBottom: 36,
            }}
          >
            From Hackathon Champion to community-built tool.
          </div>
          <div style={{display: 'flex', gap: 14}}>
            {TOPICS.map((t) => (
              <div
                key={t}
                style={{
                  fontFamily: 'JetBrains Mono, monospace',
                  fontSize: 18,
                  color: INK,
                  background: 'rgba(237,237,237,0.05)',
                  border: `1px solid ${RULE}`,
                  borderRadius: 999,
                  padding: '9px 22px',
                }}
              >
                {t}
              </div>
            ))}
          </div>
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            border: `1px solid ${ACCENT}`,
            borderRadius: 18,
            padding: '30px 44px',
            background: 'rgba(63,185,80,0.06)',
          }}
        >
          <div
            style={{
              fontFamily: 'Inter, sans-serif',
              fontWeight: 700,
              fontSize: 40,
              color: INK,
            }}
          >
            {date}
          </div>
          <div style={{width: 1, height: 46, background: RULE}} />
          <div
            style={{
              fontFamily: 'JetBrains Mono, monospace',
              fontWeight: 700,
              fontSize: 52,
              color: ACCENT,
              letterSpacing: '-0.01em',
            }}
          >
            {time}
          </div>
          <div style={{width: 1, height: 46, background: RULE}} />
          <div
            style={{
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: 20,
              color: MUTED,
            }}
          >
            @PortaldotDevKit
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
