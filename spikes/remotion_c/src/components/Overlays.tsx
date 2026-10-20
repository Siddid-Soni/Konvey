// HTML overlay components. Pure functions of (absolute frame, storyboard data).
import React from "react";
import { Easing, interpolate, spring, useVideoConfig } from "remotion";
import { FPS, LETTERBOX, TITLE, type Beat, type Card as CardT, type Center as CenterT } from "../storyboard";
import { COLORS, FONT } from "../theme";
import { TUMBLE, worldAt } from "../timeline";
import { Tex } from "./Tex";

const clampOpt = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const ease = Easing.bezier(0.65, 0, 0.35, 1);

/** 0→1 enter / 1→0 exit envelope for something visible in [t0, t1] (seconds). */
const envelope = (t: number, t0: number, t1: number, fadeIn = 0.45, fadeOut = 0.35) =>
  Math.min(interpolate(t, [t0, t0 + fadeIn], [0, 1], { ...clampOpt, easing: ease }), interpolate(t, [t1 - fadeOut, t1], [1, 0], { ...clampOpt, easing: ease }));

// ------------------------------------------------------------- letterbox
export const Letterbox: React.FC<{ frame: number }> = ({ frame }) => {
  const t = frame / FPS;
  const { height } = useVideoConfig();
  const closed = height / 2;
  const h = t < LETTERBOX.close[0]
    ? interpolate(t, LETTERBOX.open, [closed, LETTERBOX.bar], { ...clampOpt, easing: ease })
    : interpolate(t, LETTERBOX.close, [LETTERBOX.bar, closed], { ...clampOpt, easing: ease });
  const bar: React.CSSProperties = { position: "absolute", left: 0, right: 0, height: h, background: "#000" };
  return (
    <>
      <div style={{ ...bar, top: 0 }} />
      <div style={{ ...bar, bottom: 0 }} />
    </>
  );
};

// ------------------------------------------------------------- kinetic title
export const KineticTitle: React.FC<{ frame: number }> = ({ frame }) => {
  const t = frame / FPS;
  const shrink = interpolate(t, [TITLE.shrinkAt, TITLE.shrinkAt + 1.1], [0, 1], { ...clampOpt, easing: ease });
  const left = interpolate(shrink, [0, 1], [960, 96]);
  const top = interpolate(shrink, [0, 1], [540, 96]);
  const tr = interpolate(shrink, [0, 1], [-50, 0]);
  const scale = interpolate(shrink, [0, 1], [1, 0.34]);
  let idx = 0;
  const underline = interpolate(t, [2.3, 3.0], [0, 1], { ...clampOpt, easing: ease });
  return (
    <div
      style={{
        position: "absolute", left, top, transform: `translate(${tr}%, ${tr}%) scale(${scale})`, transformOrigin: "0 0",
        fontFamily: FONT, fontWeight: 700, fontSize: 92, lineHeight: 1.12, color: COLORS.text, textAlign: shrink > 0.5 ? "left" : "center",
        whiteSpace: "nowrap", letterSpacing: -1,
      }}
    >
      {TITLE.lines.map((line, li) => (
        <div key={li}>
          {line.map((w) => {
            const i = idx++;
            const sp = spring({ frame: frame - 12 - i * 5, fps: FPS, config: { damping: 14, mass: 0.7 } });
            const hl = TITLE.highlight.includes(w);
            return (
              <span key={w + i} style={{ display: "inline-block", marginRight: "0.26em", position: "relative", opacity: sp, transform: `translateY(${(1 - sp) * 60}px) rotate(${(1 - sp) * -6}deg)`, filter: `blur(${(1 - sp) * 8}px)`, color: hl ? COLORS.accent : undefined }}>
                {w}
                {hl && (
                  <span style={{ position: "absolute", left: 0, right: 0, bottom: 4, height: 7, background: COLORS.accent, transform: `scaleX(${underline})`, transformOrigin: "0 50%", borderRadius: 4 }} />
                )}
              </span>
            );
          })}
        </div>
      ))}
    </div>
  );
};

// ------------------------------------------------------------- caption
export const Caption: React.FC<{ beat: Beat; frame: number }> = ({ beat, frame }) => {
  if (!beat.caption) return null;
  const t = frame / FPS;
  const env = envelope(t, beat.start + 0.15, beat.end);
  if (env <= 0) return null;
  const words = beat.caption.split(" ");
  return (
    <div style={{ position: "absolute", left: 0, right: 0, bottom: LETTERBOX.bar + 40, display: "flex", justifyContent: "center", opacity: env }}>
      <div style={{ maxWidth: 1560, textAlign: "center", fontFamily: FONT, fontSize: 38, lineHeight: 1.35, color: COLORS.text, textShadow: "0 2px 12px rgba(0,0,0,0.9)", padding: "10px 28px", background: "rgba(8,10,14,0.55)", borderRadius: 14 }}>
        {words.map((w, i) => {
          const k = interpolate(t, [beat.start + 0.15 + i * 0.035, beat.start + 0.45 + i * 0.035], [0, 1], clampOpt);
          return <span key={i} style={{ display: "inline-block", opacity: k, transform: `translateY(${(1 - k) * 12}px)`, marginRight: "0.28em" }}>{w}</span>;
        })}
      </div>
    </div>
  );
};

// ------------------------------------------------------------- right-hand card
const fmt = (v: number, digits = 2) => (digits === 0 ? Math.round(v).toLocaleString("en-US") : v.toFixed(digits));

export const Card: React.FC<{ beat: Beat; card: CardT; frame: number }> = ({ beat, card, frame }) => {
  const t = frame / FPS;
  const t0 = beat.start + (card.at ?? 0.3);
  const env = envelope(t, t0, beat.end, 0.55, 0.3);
  if (env <= 0) return null;
  const s = worldAt(frame);
  return (
    <div
      style={{
        position: "absolute", right: 96, top: 200, width: 540, padding: "30px 34px", borderRadius: 22, background: COLORS.card,
        border: `1.5px solid ${COLORS.cardBorder}`, boxShadow: "0 20px 60px rgba(0,0,0,0.45)", fontFamily: FONT, color: COLORS.text,
        opacity: env, transform: `translateX(${(1 - env) * 70}px)`, filter: `blur(${(1 - env) * 6}px)`, boxSizing: "border-box",
      }}
    >
      <div style={{ fontSize: 26, fontWeight: 700, letterSpacing: 3, textTransform: "uppercase", color: COLORS.accent }}>{card.heading}</div>
      {card.tex && <div style={{ marginTop: 18, marginBottom: 10 }}><Tex tex={card.tex} size={48} maxWidth={540 - 68} /></div>}
      {card.readouts?.map((r) => (
        <div key={r.label} style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 14, gap: 16 }}>
          <span style={{ fontSize: 24, color: COLORS.muted, whiteSpace: "nowrap" }}>{r.label}</span>
          <span style={{ fontSize: 42, fontWeight: 700, fontVariantNumeric: "tabular-nums", color: COLORS.text }}>{fmt(s.readouts[r.value], r.digits)}</span>
        </div>
      ))}
      {card.chart === "runningMean" && <RunningMeanChart n={s.tumble?.n ?? 0} />}
    </div>
  );
};

const RunningMeanChart: React.FC<{ n: number }> = ({ n }) => {
  if (!TUMBLE) return null;
  const W = 470, H = 190, padL = 46, padB = 30;
  const nMax = TUMBLE.areas.length;
  const x = (k: number) => padL + (Math.log10(k) / Math.log10(nMax)) * (W - padL - 8);
  const y = (v: number) => (H - padB) - ((v - 1.0) / (2.0 - 1.0)) * (H - padB - 8);
  const pts: string[] = [];
  const ks = new Set<number>();
  for (let i = 0; i <= 240; i++) ks.add(Math.max(1, Math.round(Math.pow(nMax, i / 240))));
  for (const k of [...ks].sort((a, b) => a - b)) if (k <= n) pts.push(`${x(k).toFixed(1)},${y(TUMBLE.runningMean[k]).toFixed(1)}`);
  return (
    <svg width={W} height={H} style={{ marginTop: 18, display: "block" }}>
      {[1.0, 1.5, 2.0].map((v) => (
        <g key={v}>
          <line x1={padL} x2={W - 8} y1={y(v)} y2={y(v)} stroke={v === 1.5 ? COLORS.accent : "#2b3542"} strokeDasharray={v === 1.5 ? "8 6" : undefined} strokeWidth={v === 1.5 ? 2 : 1} />
          <text x={padL - 10} y={y(v) + 7} fill={v === 1.5 ? COLORS.accent : COLORS.muted} fontSize={20} textAnchor="end" fontFamily={FONT}>{v.toFixed(1)}</text>
        </g>
      ))}
      {[1, 10, 100, 1000].map((k) => (
        <text key={k} x={x(k)} y={H - 6} fill={COLORS.muted} fontSize={18} textAnchor="middle" fontFamily={FONT}>{k.toLocaleString("en-US")}</text>
      ))}
      <polyline points={pts.join(" ")} fill="none" stroke="#93c5fd" strokeWidth={3} strokeLinejoin="round" />
      {n > 0 && <circle cx={x(n)} cy={y(TUMBLE.runningMean[n])} r={6} fill="#ffffff" />}
    </svg>
  );
};

// ------------------------------------------------------------- centre formula (payoff / summary)
export const Center: React.FC<{ beat: Beat; center: CenterT; frame: number; panel?: boolean }> = ({ beat, center, frame, panel }) => {
  const t = frame / FPS;
  const rel = t - beat.start;
  const env = envelope(t, beat.start + center.stages[0].at, beat.end + 10, 0.5, 0.3);
  return (
    <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", fontFamily: FONT, color: COLORS.text }}>
      <div style={{ position: "relative", width: 1600, height: 170, opacity: panel ? env : 1 }}>
        {center.stages.map((st, i) => {
          const next = center.stages[i + 1]?.at ?? 1e6;
          const kin = interpolate(rel, [st.at, st.at + 0.5], [0, 1], { ...clampOpt, easing: ease });
          const kout = interpolate(rel, [next - 0.05, next + 0.4], [0, 1], { ...clampOpt, easing: ease });
          const o = kin * (1 - kout);
          if (o <= 0.001) return null;
          return (
            <div key={i} style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", opacity: o, transform: `translateY(${(1 - kin) * 40 - kout * 40}px) scale(${0.96 + 0.04 * kin})`, filter: `blur(${(1 - kin) * 8 + kout * 8}px)` }}>
              <Tex tex={st.tex} size={panel ? 76 : 88} maxWidth={1500} style={{ transformOrigin: "50% 50%" }} />
            </div>
          );
        })}
      </div>
      {center.kinetic && (
        <div style={{ marginTop: 60, fontSize: 64, fontWeight: 700, whiteSpace: "nowrap" }}>
          {center.kinetic.text.split(" ").map((w, i) => {
            const sp = spring({ frame: Math.round((rel - center.kinetic!.at) * FPS) - i * 4, fps: FPS, config: { damping: 12, mass: 0.6 } });
            const hl = center.kinetic!.highlight.includes(w);
            return (
              <span key={i} style={{ display: "inline-block", marginRight: "0.3em", opacity: Math.min(1, sp), transform: `translateY(${(1 - sp) * 50}px) scale(${hl ? 0.6 + 0.6 * sp : 1})`, color: hl ? COLORS.accent : COLORS.text, fontSize: hl ? 96 : undefined }}>{w}</span>
            );
          })}
        </div>
      )}
      {center.note && (
        <div style={{ marginTop: 40, fontSize: 34, color: COLORS.muted, whiteSpace: "pre", opacity: interpolate(rel, [center.note.at, center.note.at + 0.5], [0, 1], clampOpt) }}>{center.note.text}</div>
      )}
    </div>
  );
};
