export function playbackStartFrame(currentFrame: number, lastFrame: number): number {
  return currentFrame >= lastFrame ? 0 : currentFrame;
}
