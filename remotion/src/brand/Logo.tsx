import React from 'react';
import {AbsoluteFill} from 'remotion';
import {loadFont} from '@remotion/google-fonts/Inter';

loadFont();

// Wordmark: "PDK" all-caps + green circle to the RIGHT of K as the period.
// The dot is a real geometric circle, sized proportionally to the cap
// height so it reads as an integrated period, not a floating decoration.

const BG = '#0a0c10';
const INK = '#ededed';
const ACCENT = '#3fb950';

// `gap`/`dotOffsetY` are optional: every brand still already omits one or the
// other, and both default to 0 (which is what they silently rendered as before).
type Size = {font: number; dot: number; gap?: number; dotOffsetY?: number};

function Wordmark({size, dotColor}: {size: Size; dotColor: string}) {
  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'baseline',
        fontFamily: 'Inter, sans-serif',
        fontWeight: 900,
        fontSize: size.font,
        letterSpacing: '-0.045em',
        color: INK,
        lineHeight: 1,
      }}
    >
      <span>PDK</span>
      <span
        style={{
          display: 'inline-block',
          width: size.dot,
          height: size.dot,
          borderRadius: '50%',
          background: dotColor,
          marginLeft: size.gap ?? 0,
          transform: `translateY(${size.dotOffsetY ?? 0}px)`,
        }}
      />
    </div>
  );
}

const bigSize: Size = {font: 340, dot: 78, gap: 22, dotOffsetY: -4};
const midSize: Size = {font: 200, dot: 46, gap: 12, dotOffsetY: -2};

export const LogoSquare: React.FC = () => {
  return (
    <AbsoluteFill
      style={{backgroundColor: BG, justifyContent: 'center', alignItems: 'center'}}
    >
      <Wordmark size={bigSize} dotColor={ACCENT} />
    </AbsoluteFill>
  );
};

export const LogoHorizontal: React.FC = () => {
  return (
    <AbsoluteFill
      style={{backgroundColor: BG, justifyContent: 'center', alignItems: 'center'}}
    >
      <Wordmark size={midSize} dotColor={ACCENT} />
    </AbsoluteFill>
  );
};

export const LogoMono: React.FC = () => {
  return (
    <AbsoluteFill
      style={{backgroundColor: BG, justifyContent: 'center', alignItems: 'center'}}
    >
      <Wordmark size={bigSize} dotColor={INK} />
    </AbsoluteFill>
  );
};

export {Wordmark};
export type {Size};
