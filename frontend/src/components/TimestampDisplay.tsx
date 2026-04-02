import { useState, useEffect, useRef } from 'react';

function formatTime(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60);
  const s = Math.floor(totalSeconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function parseTime(str: string): number | null {
  const parts = str.split(':');
  if (parts.length !== 2) return null;
  const m = parseInt(parts[0], 10);
  const s = parseInt(parts[1], 10);
  if (isNaN(m) || isNaN(s) || s > 59 || m < 0 || s < 0) return null;
  return m * 60 + s;
}

interface Props {
  currentTime: number;
  autoMode: boolean;
  onFreeze: () => void;
  onManualSet: (seconds: number) => void;
  onResetAuto: () => void;
}

export default function TimestampDisplay({
  currentTime,
  autoMode,
  onFreeze,
  onManualSet,
  onResetAuto,
}: Props) {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  function handleClick() {
    if (autoMode) {
      onFreeze();
    }
    setEditValue(formatTime(currentTime));
    setIsEditing(true);
  }

  function handleSubmit() {
    const parsed = parseTime(editValue);
    if (parsed !== null) {
      onManualSet(parsed);
    }
    setIsEditing(false);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter') handleSubmit();
    if (e.key === 'Escape') {
      setIsEditing(false);
      onResetAuto();
    }
  }

  return (
    <div className="flex items-center gap-2 px-3 py-2 bg-dark-card border border-dark-border rounded-lg text-sm">
      <span className="text-gray-400">⏱️</span>

      {isEditing ? (
        <input
          ref={inputRef}
          type="text"
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onBlur={handleSubmit}
          onKeyDown={handleKeyDown}
          placeholder="MM:SS"
          className="w-16 bg-dark-bg border border-accent rounded px-2 py-0.5 text-gray-100 text-center text-sm focus:outline-none"
        />
      ) : (
        <button
          onClick={handleClick}
          className="text-gray-100 font-mono hover:text-accent transition-colors"
        >
          {formatTime(currentTime)}
        </button>
      )}

      {/* Status indicator */}
      {autoMode && !isEditing && (
        <span className="flex items-center gap-1 text-xs text-gray-500">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
          </span>
          auto
        </span>
      )}
      {!autoMode && !isEditing && (
        <span className="flex items-center gap-1 text-xs text-gray-500">
          🔒 frozen
          <button
            onClick={onResetAuto}
            className="ml-1 text-accent hover:text-accent-hover transition-colors underline"
          >
            reset
          </button>
        </span>
      )}
    </div>
  );
}
