import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { iris } from "@remotion/transitions/iris";
import { wipe } from "@remotion/transitions/wipe";
import React, { useEffect, useState } from "react";
import { AbsoluteFill, continueRender, delayRender, useCurrentFrame, useVideoConfig } from "remotion";
import { Caption, Card, Center, KineticTitle, Letterbox } from "./components/Overlays";
import { World3D } from "./components/World3D";
import { BEATS, FPS, SCENES, type SceneId } from "./storyboard";
import { COLORS, FONT } from "./theme";

/** Scene windows on the absolute timeline, derived from the beats + transitions. */
export const sceneWindows = () => {
  const f = (s: number) => Math.round(s * FPS);
  return SCENES.map((sc, i) => {
    const beats = BEATS.filter((b) => b.scene === sc.id);
    const tin = sc.transitionIn?.dur ?? 0;
    const tout = SCENES[i + 1]?.transitionIn?.dur ?? 0;
    const startF = f(beats[0].start) - (tin ? f(tin / 2) : 0);
    const endF = f(beats[beats.length - 1].end) + (tout ? f(tout / 2) : 0);
    return { ...sc, beats, startF, durF: endF - startF, tinF: tin ? f(tin) : 0 };
  });
};

const useFonts = () => {
  const [handle] = useState(() => delayRender("fonts"));
  useEffect(() => {
    const faces = ["400 40px 'Noto Sans'", "700 40px 'Noto Sans'", "40px KaTeX_Main", "italic 40px KaTeX_Math", "40px KaTeX_Size1", "40px KaTeX_Size2", "40px KaTeX_AMS"];
    Promise.all(faces.map((f) => document.fonts.load(f))).then(() => document.fonts.ready).then(() => continueRender(handle));
  }, [handle]);
};

const SceneView: React.FC<{ id: SceneId; startF: number; kind: "world" | "formula" }> = ({ id, startF, kind }) => {
  const frame = useCurrentFrame() + startF;
  const beats = BEATS.filter((b) => b.scene === id);
  const t = frame / FPS;
  return (
    <AbsoluteFill style={{ background: COLORS.bg }}>
      {kind === "world" ? <World3D frameOffset={startF} /> : <FormulaBackdrop frame={frame} />}
      {beats.map((b) => (
        <React.Fragment key={b.id}>
          {b.card && <Card beat={b} card={b.card} frame={frame} />}
          {b.center && t >= b.start - 0.1 && (
            kind === "world"
              ? <SummaryPanel frame={frame} start={b.start}><Center beat={b} center={b.center} frame={frame} panel /></SummaryPanel>
              : <Center beat={b} center={b.center} frame={frame} />
          )}
          <Caption beat={b} frame={frame} />
        </React.Fragment>
      ))}
    </AbsoluteFill>
  );
};

const SummaryPanel: React.FC<{ frame: number; start: number; children: React.ReactNode }> = ({ frame, start, children }) => {
  const k = Math.min(1, Math.max(0, (frame / FPS - start) / 0.6));
  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left: 160, right: 160, top: 300, bottom: 300, borderRadius: 28, background: "rgba(10,13,18,0.82)", border: `1.5px solid ${COLORS.cardBorder}`, opacity: k, transform: `scale(${0.94 + 0.06 * k})` }} />
      {children}
    </AbsoluteFill>
  );
};

/** Background for the payoff: the shadow hexagon, outlined, slowly turning. */
const FormulaBackdrop: React.FC<{ frame: number }> = ({ frame }) => {
  const a = frame * 0.25;
  const hex = Array.from({ length: 6 }, (_, i) => {
    const t = (Math.PI / 3) * i;
    return `${960 + 430 * Math.cos(t)},${540 + 430 * Math.sin(t)}`;
  }).join(" ");
  return (
    <AbsoluteFill style={{ background: `radial-gradient(ellipse at 50% 45%, #18202b 0%, ${COLORS.bg} 70%)` }}>
      <svg width={1920} height={1080} style={{ position: "absolute", inset: 0, opacity: 0.16 }}>
        <polygon points={hex} fill="none" stroke={COLORS.accent} strokeWidth={3} transform={`rotate(${a} 960 540)`} />
        <polygon points={hex} fill="none" stroke={COLORS.cube} strokeWidth={2} transform={`rotate(${-a * 0.7} 960 540) scale(1)`} style={{ transformOrigin: "960px 540px", transform: `rotate(${-a * 0.7}deg) scale(0.7)` }} />
      </svg>
    </AbsoluteFill>
  );
};

export const CubeShadow: React.FC = () => {
  useFonts();
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const windows = sceneWindows();
  const items: React.ReactNode[] = [];
  windows.forEach((w, i) => {
    if (i > 0 && w.transitionIn) {
      const presentation = w.transitionIn.type === "wipe" ? wipe({ direction: "from-right" }) : iris({ width, height });
      items.push(<TransitionSeries.Transition key={`t${i}`} presentation={presentation as never} timing={linearTiming({ durationInFrames: w.tinF })} />);
    }
    items.push(
      <TransitionSeries.Sequence key={w.id} durationInFrames={w.durF}>
        <SceneView id={w.id} startF={w.startF} kind={w.kind} />
      </TransitionSeries.Sequence>,
    );
  });
  return (
    <AbsoluteFill style={{ background: COLORS.bg, fontFamily: FONT }}>
      <TransitionSeries>{items}</TransitionSeries>
      <KineticTitle frame={frame} />
      <Letterbox frame={frame} />
    </AbsoluteFill>
  );
};
