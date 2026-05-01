import type { Checkpoint } from '../types';

interface Props {
  checkpoints: Checkpoint[];
  videoDuration: number;
  onCheckpointClick: (cp: Checkpoint) => void;
}

export function CheckpointMarkers({
  checkpoints,
  videoDuration,
  onCheckpointClick,
}: Props) {
  if (!videoDuration || checkpoints.length === 0) return null;

  return (
    <div className="relative h-5 bg-gray-100 rounded-full mx-2 my-1">
      {checkpoints.map((cp) => {
        const left = (cp.timestamp_seconds / videoDuration) * 100;
        return (
          <button
            key={cp.id}
            className="absolute w-3 h-3 rounded-full bg-blue-500 hover:bg-blue-700 -translate-x-1/2 top-1 transition-colors"
            style={{ left: `${left}%` }}
            title={cp.topic_label}
            onClick={() => onCheckpointClick(cp)}
          />
        );
      })}
    </div>
  );
}
