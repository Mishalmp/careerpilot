"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useSyncExternalStore } from "react";

export type Theme = "light" | "dark" | "system";
export type Density = "comfortable" | "compact";

type ThemeState = {
  theme: Theme;
  /** The theme actually shown (system resolved to light or dark). */
  resolved: "light" | "dark";
  density: Density;
  setTheme: (t: Theme) => void;
  setDensity: (d: Density) => void;
};

const ThemeContext = createContext<ThemeState | null>(null);
const ONE_YEAR = 60 * 60 * 24 * 365;

function readCookie(name: string): string | null {
  const m = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return m ? decodeURIComponent(m[1]) : null;
}
function writeCookie(name: string, value: string) {
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=${ONE_YEAR}; SameSite=Lax`;
}

// The cookies are the stored preference. They are read through useSyncExternalStore so the server
// render ("system"/"comfortable") and the first client render agree, and the real value then
// replaces it without a hydration mismatch. public/theme-init.js has already styled <html>.
const listeners = new Set<() => void>();
function subscribe(callback: () => void) {
  listeners.add(callback);
  return () => listeners.delete(callback);
}
function notify() {
  listeners.forEach((l) => l());
}

const themeSnapshot = (): Theme => {
  const t = readCookie("cp-theme");
  return t === "light" || t === "dark" || t === "system" ? t : "system";
};
const densitySnapshot = (): Density => (readCookie("cp-density") === "compact" ? "compact" : "comfortable");

const MEDIA = "(prefers-color-scheme: dark)";
function subscribeSystem(callback: () => void) {
  const query = window.matchMedia(MEDIA);
  query.addEventListener("change", callback);
  return () => query.removeEventListener("change", callback);
}
const systemDarkSnapshot = () => window.matchMedia(MEDIA).matches;

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const theme = useSyncExternalStore(subscribe, themeSnapshot, () => "system" as Theme);
  const density = useSyncExternalStore(subscribe, densitySnapshot, () => "comfortable" as Density);
  const systemDark = useSyncExternalStore(subscribeSystem, systemDarkSnapshot, () => false);
  const resolved: "light" | "dark" = theme === "dark" || (theme === "system" && systemDark) ? "dark" : "light";

  // Keep <html> in sync with the preference (the init script did the first paint).
  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", resolved === "dark");
    root.style.colorScheme = resolved;
    root.dataset.density = density;
  }, [resolved, density]);

  const setTheme = useCallback((t: Theme) => {
    writeCookie("cp-theme", t);
    notify();
  }, []);
  const setDensity = useCallback((d: Density) => {
    writeCookie("cp-density", d);
    notify();
  }, []);

  const value = useMemo(
    () => ({ theme, resolved, density, setTheme, setDensity }),
    [theme, resolved, density, setTheme, setDensity],
  );
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeState {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used inside ThemeProvider");
  return ctx;
}
