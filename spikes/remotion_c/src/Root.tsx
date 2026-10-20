import React from "react";
import { Composition } from "remotion";
import { FPS, HEIGHT, TOTAL_SECONDS, WIDTH } from "./storyboard";
import { CubeShadow } from "./Video";

export const Root: React.FC = () => (
  <Composition id="CubeShadow" component={CubeShadow} durationInFrames={Math.round(TOTAL_SECONDS * FPS)} fps={FPS} width={WIDTH} height={HEIGHT} />
);
