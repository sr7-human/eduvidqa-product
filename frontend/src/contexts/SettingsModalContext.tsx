import { createContext, useContext, useState, type ReactNode } from 'react';

interface SettingsModalCtx {
  isOpen: boolean;
  openSettings: () => void;
  closeSettings: () => void;
}

const Ctx = createContext<SettingsModalCtx>({
  isOpen: false,
  openSettings: () => {},
  closeSettings: () => {},
});

// eslint-disable-next-line react-refresh/only-export-components
export function useSettingsModal(): SettingsModalCtx {
  return useContext(Ctx);
}

/**
 * Holds the open/close state for a global Settings modal so users can open
 * Settings from anywhere (e.g. mid-video) WITHOUT navigating away — which
 * would unmount the player and restart the video. The modal itself is rendered
 * by <GlobalSettingsModal/> (kept separate to avoid a circular import with the
 * Navbar, which consumes this context).
 */
export function SettingsModalProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  return (
    <Ctx.Provider
      value={{ isOpen, openSettings: () => setIsOpen(true), closeSettings: () => setIsOpen(false) }}
    >
      {children}
    </Ctx.Provider>
  );
}
