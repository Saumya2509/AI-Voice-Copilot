// Light / dark switch. Follows prefers-color-scheme on first load, then remembers the choice.
// Swapping animates colours for 200 ms with no layout shift.
import { useEffect, useState } from "react";
import { Icon } from "./Icon";

type Theme = "light" | "dark";

export function useTheme(): [Theme, (t: Theme) => void] {
  const [theme, set] = useState<Theme>(() => (document.documentElement.dataset.theme as Theme) || "light");
  useEffect(() => {
    const root = document.documentElement;
    if (root.dataset.theme === theme) return;
    root.classList.add("theme-swap");
    root.dataset.theme = theme;
    const t = window.setTimeout(() => root.classList.remove("theme-swap"), 220);
    try {
      localStorage.setItem("tadka.theme", theme);
    } catch { /* storage may be blocked */ }
    return () => window.clearTimeout(t);
  }, [theme]);
  return [theme, set];
}

export function ThemeSwitch({ compact = false }: { compact?: boolean }) {
  const [theme, setTheme] = useTheme();
  const dark = theme === "dark";
  return (
    <button
      role="switch"
      aria-checked={dark}
      aria-label="Dark theme"
      onClick={() => setTheme(dark ? "light" : "dark")}
      className="flex items-center gap-3 text-sm text-muted hover:text-ink"
    >
      <Icon name={dark ? "moon" : "sun"} />
      {!compact && <span className="whitespace-nowrap">{dark ? "Dark" : "Light"}</span>}
    </button>
  );
}
