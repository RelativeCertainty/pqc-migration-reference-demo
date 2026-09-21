import { readFileSync } from 'node:fs';
import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useState } from 'react';
import { ThemeControl, themePreferenceKey, useWorkspaceTheme } from './theme';

function ThemeHarness() {
  const { theme, changeTheme } = useWorkspaceTheme();
  const [answer, setAnswer] = useState('');
  return <main className="app-theme" data-theme={theme} data-testid="workspace"><ThemeControl theme={theme} onChange={changeTheme} /><label>Draft answer<input value={answer} onChange={event => setAnswer(event.target.value)} /></label></main>;
}

beforeEach(() => { window.localStorage.clear(); });
afterEach(() => { vi.restoreAllMocks(); window.localStorage.clear(); });

describe('shared authenticated workspace appearance', () => {
  it('starts dark, persists the explicit preference and preserves unsaved form content and route', () => {
    history.replaceState(null, '', '#discovery-request?assessment=example&request=example');
    const route = window.location.href;
    const view = render(<ThemeHarness />);
    expect(screen.getByTestId('workspace')).toHaveAttribute('data-theme', 'dark');
    fireEvent.change(screen.getByLabelText('Draft answer'), { target: { value: 'Two products; owner still unknown' } });
    fireEvent.change(screen.getByRole('combobox', { name: 'Theme' }), { target: { value: 'light' } });
    expect(screen.getByTestId('workspace')).toHaveAttribute('data-theme', 'light');
    expect(screen.getByLabelText('Draft answer')).toHaveValue('Two products; owner still unknown');
    expect(window.location.href).toBe(route);
    expect(window.localStorage.getItem(themePreferenceKey)).toBe('light');
    view.unmount(); render(<ThemeHarness />);
    expect(screen.getByTestId('workspace')).toHaveAttribute('data-theme', 'light');
  });

  it('honors only valid preferences and synchronizes another tab without remounting answers', () => {
    window.localStorage.setItem(themePreferenceKey, 'invalid');
    render(<ThemeHarness />);
    fireEvent.change(screen.getByLabelText('Draft answer'), { target: { value: 'Keep this draft' } });
    expect(screen.getByTestId('workspace')).toHaveAttribute('data-theme', 'dark');
    window.localStorage.setItem(themePreferenceKey, 'light');
    fireEvent(window, new StorageEvent('storage', { key: themePreferenceKey, newValue: 'light' }));
    expect(screen.getByTestId('workspace')).toHaveAttribute('data-theme', 'light');
    expect(screen.getByLabelText('Draft answer')).toHaveValue('Keep this draft');
  });

  it('still changes appearance when browser preference storage is unavailable', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('Storage blocked'); });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('Storage blocked'); });
    render(<ThemeHarness />);
    fireEvent.change(screen.getByRole('combobox', { name: 'Theme' }), { target: { value: 'light' } });
    expect(screen.getByTestId('workspace')).toHaveAttribute('data-theme', 'light');
  });
});

const palette = readFileSync('src/theme.css', 'utf8');
const color = (token: string, mode: number) => {
  const match = palette.match(new RegExp(`--${token}: light-dark\\((#[0-9a-f]{6}), (#[0-9a-f]{6})\\)`));
  if (!match) throw new Error(`Missing palette token: ${token}`);
  return match[mode + 1];
};
function luminance(hex: string) {
  const rgb = hex.slice(1).match(/../g)!.map(value => Number.parseInt(value, 16) / 255).map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4);
  return .2126 * rgb[0] + .7152 * rgb[1] + .0722 * rgb[2];
}
function contrast(first: string, second: string) {
  const a = luminance(first), b = luminance(second);
  return (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
}

describe('shared form palette contrast guardrails', () => {
  for (const [mode, label] of ['light', 'dark'].entries()) {
    it(`keeps text, controls and focus legible in ${label} mode`, () => {
      for (const [foreground, background] of [
        ['ink', 'surface'], ['ink', 'control'], ['ink', 'accent-soft'], ['muted', 'surface'],
        ['muted', 'surface-muted'], ['teal', 'surface'], ['accent-ink', 'teal'],
        ['warning-ink', 'warning-bg'], ['error-ink', 'error-bg'], ['success-ink', 'success-bg'],
      ]) expect(contrast(color(foreground, mode), color(background, mode)), `${foreground} on ${background}`).toBeGreaterThanOrEqual(4.5);
      expect(contrast(color('line-strong', mode), color('control', mode))).toBeGreaterThanOrEqual(3);
      expect(contrast(color('teal', mode), color('surface', mode))).toBeGreaterThanOrEqual(3);
    });
  }
});
