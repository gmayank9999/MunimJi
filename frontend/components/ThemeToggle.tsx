"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

type Theme = "dark" | "light";

function applyTheme(theme: Theme) {
  document.documentElement.setAttribute("data-theme", theme);
  try {
    localStorage.setItem("munimji-theme", theme);
  } catch {
    // private browsing / blocked storage - theme just won't persist across reloads
  }
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme | null>(null);

  useEffect(() => {
    // reads the value the anti-FOUC inline script (see layout.tsx) already set on
    // <html> before hydration - deferred to a microtask so this isn't a synchronous
    // setState-in-effect (only React-driven state changes belong there directly).
    Promise.resolve().then(() => {
      const current = document.documentElement.getAttribute("data-theme");
      setTheme(current === "light" ? "light" : "dark");
    });
  }, []);

  if (theme === null) {
    // avoids a mismatched icon flash before the inline anti-FOUC script's choice is read
    return <div className="h-8 w-8" />;
  }

  const next: Theme = theme === "dark" ? "light" : "dark";

  return (
    <button
      type="button"
      onClick={() => {
        applyTheme(next);
        setTheme(next);
      }}
      aria-label={`Switch to ${next} mode`}
      title={`Switch to ${next} mode`}
      className="flex h-8 w-8 items-center justify-center rounded-full border border-border text-muted transition-colors hover:border-saffron hover:text-saffron"
    >
      {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  );
}
