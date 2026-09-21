import { useEffect, useLayoutEffect, useState } from 'react';

export type WorkspaceTheme = 'dark' | 'light';
export const themePreferenceKey = 'pqc.workspace.theme.v1';

export function useDocumentTheme(theme: WorkspaceTheme, authenticated: boolean) {
  useLayoutEffect(() => {
    if (!authenticated) return;
    document.documentElement.dataset.workspaceTheme = theme;
    return () => { delete document.documentElement.dataset.workspaceTheme; };
  }, [theme, authenticated]);
}

function readTheme(): WorkspaceTheme {
  try { return window.localStorage.getItem(themePreferenceKey) === 'light' ? 'light' : 'dark'; }
  catch { return 'dark'; }
}

// Only a display preference is persisted. Responses, identity and workflow state
// remain under the existing C# authority and are never stored here.
export function useWorkspaceTheme() {
  const [theme, setTheme] = useState<WorkspaceTheme>(readTheme);
  useEffect(() => {
    const synchronize = (event: StorageEvent) => {
      if (event.key === themePreferenceKey || event.key === null) setTheme(readTheme());
    };
    window.addEventListener('storage', synchronize);
    return () => window.removeEventListener('storage', synchronize);
  }, []);
  function changeTheme(next: WorkspaceTheme) {
    setTheme(next);
    try { window.localStorage.setItem(themePreferenceKey, next); }
    catch { /* A blocked preference store must not prevent using the form. */ }
  }
  return { theme, changeTheme };
}

export function ThemeControl({ theme, onChange }: { theme: WorkspaceTheme; onChange: (theme: WorkspaceTheme) => void }) {
  return <label className="theme-control"><span>Theme</span><select aria-label="Theme" value={theme} onChange={event => onChange(event.target.value as WorkspaceTheme)}><option value="dark">Dark</option><option value="light">Light</option></select></label>;
}
