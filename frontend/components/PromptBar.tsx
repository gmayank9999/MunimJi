"use client";

import { useState } from "react";

const CHIPS = [
  "Check all pending payments and take necessary action",
  "What's my exposure?",
  "Why did you escalate Orion?",
  "Pause Bluepeak till Monday",
];

export function PromptBar({
  onRun,
  running,
}: {
  onRun: (prompt: string) => void;
  running: boolean;
}) {
  const [value, setValue] = useState("");

  function submit(prompt: string) {
    if (!prompt.trim() || running) return;
    onRun(prompt.trim());
  }

  return (
    <div className="rounded-xl border border-border bg-surface px-5 py-4">
      <form
        className="flex flex-col gap-3 sm:flex-row sm:items-center"
        onSubmit={(e) => {
          e.preventDefault();
          submit(value);
        }}
      >
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder='Ask MunimJi&hellip; "Check all pending payments and take necessary action"'
          disabled={running}
          className="flex-1 rounded-lg border border-border bg-background px-4 py-2 text-sm text-foreground placeholder:text-muted focus:outline-none focus:ring-1 focus:ring-saffron disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={running || !value.trim()}
          className="rounded-lg bg-saffron px-4 py-2 text-sm font-medium text-background transition-opacity disabled:opacity-40"
        >
          {running ? "Running…" : "Run"}
        </button>
      </form>
      <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted">
        {CHIPS.map((chip) => (
          <button
            key={chip}
            type="button"
            disabled={running}
            onClick={() => {
              setValue(chip);
              submit(chip);
            }}
            className="rounded-full border border-border px-3 py-1 hover:border-saffron hover:text-foreground disabled:opacity-40"
          >
            {chip}
          </button>
        ))}
      </div>
    </div>
  );
}
