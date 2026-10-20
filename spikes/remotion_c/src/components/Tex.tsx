import katex from "katex";
import "katex/dist/katex.min.css";
import React, { useLayoutEffect, useMemo, useRef, useState } from "react";

/** KaTeX inline. If `maxWidth` is given, the formula is scaled down to fit (measured in the real browser layout). */
export const Tex: React.FC<{ tex: string; size: number; color?: string; maxWidth?: number; style?: React.CSSProperties }> = ({ tex, size, color, maxWidth, style }) => {
  const html = useMemo(() => katex.renderToString(tex, { displayMode: false, throwOnError: false, output: "html" }), [tex]);
  const ref = useRef<HTMLSpanElement>(null);
  const [scale, setScale] = useState(1);
  useLayoutEffect(() => {
    if (!maxWidth || !ref.current) return;
    const w = ref.current.scrollWidth;
    setScale(w > maxWidth ? maxWidth / w : 1);
  }, [html, maxWidth, size]);
  return (
    <span
      ref={ref}
      style={{ display: "inline-block", fontSize: size, color, lineHeight: 1.2, whiteSpace: "nowrap", transform: `scale(${scale})`, transformOrigin: "0 50%", ...style }}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
};
