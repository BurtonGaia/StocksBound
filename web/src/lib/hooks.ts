import { useEffect, useState } from "react";
import type { Mode } from "./heat";

/**
 * Follows the system preference. Both modes are first-class and there is no
 * in-app override, because the brief asks for system preference and an extra
 * toggle is a control competing with the data for attention.
 *
 * Read in JS rather than CSS because the heat ramp is computed, not declared.
 */
export function useColorMode(): Mode {
  const [mode, setMode] = useState<Mode>(() =>
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light",
  );

  useEffect(() => {
    const query = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (event: MediaQueryListEvent) => setMode(event.matches ? "dark" : "light");
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  return mode;
}

/** localStorage-backed state, for the one genuine setting: palette choice. */
export function usePersistentState<T>(key: string, initial: T): [T, (value: T) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const stored = localStorage.getItem(key);
      return stored === null ? initial : (JSON.parse(stored) as T);
    } catch {
      return initial;
    }
  });

  const update = (next: T) => {
    setValue(next);
    try {
      localStorage.setItem(key, JSON.stringify(next));
    } catch {
      // A private-mode browser refusing to persist a colour preference is not
      // worth surfacing to the user.
    }
  };

  return [value, update];
}
