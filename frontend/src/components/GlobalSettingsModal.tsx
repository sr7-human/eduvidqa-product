import { Settings } from '../pages/Settings';
import { useSettingsModal } from '../contexts/SettingsModalContext';

/**
 * Renders the Settings page as a global modal overlay when opened via the
 * SettingsModal context. Kept separate from the context module to avoid a
 * circular import (Settings → Navbar → useSettingsModal).
 */
export function GlobalSettingsModal() {
  const { isOpen, closeSettings } = useSettingsModal();
  if (!isOpen) return null;
  return <Settings embedded onClose={closeSettings} />;
}
