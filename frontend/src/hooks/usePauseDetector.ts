import { useEffect, useRef } from 'react';
import type { Checkpoint } from '../types';

export function usePauseDetector(
  playerState: 'playing' | 'paused' | 'other',
  currentTimestamp: number,
  checkpoints: Checkpoint[],
  onNearCheckpoint: (cp: Checkpoint) => void,
) {
  const shownCps = useRef<Set<string>>(new Set());
  const lastTs = useRef(currentTimestamp);
  const callbackRef = useRef(onNearCheckpoint);
  callbackRef.current = onNearCheckpoint;

  useEffect(() => {
    // Detect backward seek — never trigger toast on backward seek
    const seekedBack = currentTimestamp < lastTs.current - 5;
    lastTs.current = currentTimestamp;
    if (seekedBack) return;

    if (playerState !== 'paused') return;

    // Find nearest unseen checkpoint within ±30s of current position
    const nearest = checkpoints.find(
      (cp) =>
        Math.abs(cp.timestamp_seconds - currentTimestamp) <= 30 &&
        !shownCps.current.has(cp.id),
    );

    if (nearest) {
      shownCps.current.add(nearest.id);
      callbackRef.current(nearest);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playerState, currentTimestamp]);
}
