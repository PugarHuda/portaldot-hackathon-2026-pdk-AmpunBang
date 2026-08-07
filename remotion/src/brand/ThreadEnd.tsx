import React from 'react';
import {AbsoluteFill} from 'remotion';
import {loadFont} from '@remotion/google-fonts/Inter';
import {Wordmark} from './Logo';

loadFont();

const BG = '#0a0c10';
const INK = '#ededed';
const MUTED = '#7d8590';
const ACCENT = '#3fb950';

const wordmarkSize = {font: 120, dot: 34, gap: 16, dotOffsetY: 8};

export const ThreadEnd: React.FC = () => {
  return (
    <AbsoluteFill
      style={{
        backgroundColor: BG,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 64,
      }}
    >
      <Wordmark size={wordmarkSize} dotColor={ACCENT} />
      <div
        style={{
          fontFamily: 'Inter, sans-serif',
          fontWeight: 700,
          fontSize: 96,
          color: INK,
          letterSpacing: '-0.01em',
        }}
      >
        🧵 End of thread.
      </div>
      <div
        style={{
          fontFamily: 'Inter, sans-serif',
          fontSize: 32,
          color: MUTED,
        }}
      >
        Nothing else to click. That's the whole thing.
      </div>
    </AbsoluteFill>
  );
};
