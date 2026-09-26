"use client";

import { useEffect, useRef, useState } from "react";

/**
 * A small idle animation of "MunimJi" himself - a classic Indian munim with a pagri,
 * round glasses and a ledger book - fixed to the left edge of the viewport. Purely
 * decorative (aria-hidden), floats gently and blinks/flips a page on a loop, and tilts
 * toward the cursor for a cheap-but-convincing 3D feel (gradient shading + a real
 * perspective transform, no 3D engine needed for one small mascot). Hidden below lg so
 * it never competes with content on narrower screens.
 */
export function MunimjiMascot() {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [tilt, setTilt] = useState({ x: 0, y: 0 });

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    function handleMove(e: MouseEvent) {
      const el = wrapperRef.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const dx = (e.clientX - cx) / window.innerWidth;
      const dy = (e.clientY - cy) / window.innerHeight;
      setTilt({ x: dy * -16, y: dx * 20 });
    }

    window.addEventListener("mousemove", handleMove);
    return () => window.removeEventListener("mousemove", handleMove);
  }, []);

  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed bottom-2 left-2 z-40 hidden select-none lg:block"
      style={{ perspective: "1200px" }}
    >
      <div ref={wrapperRef} className="munimji-mascot-float">
        <div
          className="munimji-mascot-tilt"
          style={{ transform: `rotateX(${tilt.x}deg) rotateY(${tilt.y}deg)` }}
        >
          <svg width="164" height="219" viewBox="0 0 96 128" fill="none" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <radialGradient id="mj-skin" cx="38%" cy="28%" r="80%">
                <stop offset="0%" stopColor="#f6d2a4" />
                <stop offset="100%" stopColor="#c9895a" />
              </radialGradient>
              <linearGradient id="mj-turban" x1="20%" y1="0%" x2="80%" y2="100%">
                <stop offset="0%" stopColor="#ffc373" />
                <stop offset="55%" stopColor="var(--saffron)" />
                <stop offset="100%" stopColor="#c67a1e" />
              </linearGradient>
              <linearGradient id="mj-kurta" x1="10%" y1="0%" x2="90%" y2="100%">
                <stop offset="0%" stopColor="var(--surface-raised)" />
                <stop offset="100%" stopColor="var(--border)" />
              </linearGradient>
              <radialGradient id="mj-shadow" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="#000000" stopOpacity="0.35" />
                <stop offset="100%" stopColor="#000000" stopOpacity="0" />
              </radialGradient>
            </defs>

            {/* shadow */}
            <ellipse cx="48" cy="122" rx="28" ry="5" fill="url(#mj-shadow)" />

            {/* body / kurta */}
            <path
              d="M24 122 C22 92 26 78 48 78 C70 78 74 92 72 122 Z"
              fill="url(#mj-kurta)"
              stroke="var(--border)"
              strokeWidth="2"
            />
            <path d="M40 82 L48 96 L56 82" stroke="var(--border)" strokeWidth="2" fill="none" />

            {/* ledger book, held in front */}
            <g className="munimji-mascot-page">
              <rect x="34" y="94" width="30" height="22" rx="2" fill="#fff8ec" stroke="var(--border)" strokeWidth="1.5" />
              <line x1="49" y1="94" x2="49" y2="116" stroke="var(--border)" strokeWidth="1" />
              <line x1="38" y1="100" x2="46" y2="100" stroke="var(--muted)" strokeWidth="1" />
              <line x1="38" y1="105" x2="46" y2="105" stroke="var(--muted)" strokeWidth="1" />
              <line x1="52" y1="100" x2="60" y2="100" stroke="var(--muted)" strokeWidth="1" />
              <line x1="52" y1="105" x2="60" y2="105" stroke="var(--muted)" strokeWidth="1" />
            </g>

            {/* head */}
            <circle cx="48" cy="54" r="22" fill="url(#mj-skin)" stroke="var(--border)" strokeWidth="2" />

            {/* pagri (turban) */}
            <path
              d="M25 46 C25 26 71 26 71 46 C71 50 66 51 48 51 C30 51 25 50 25 46 Z"
              fill="url(#mj-turban)"
              stroke="var(--border)"
              strokeWidth="2"
            />
            <path d="M25 46 Q48 40 71 46" stroke="#00000022" strokeWidth="2" fill="none" />
            <circle cx="48" cy="30" r="3.5" fill="var(--swytchcode-orange)" />
            {/* turban gloss */}
            <path d="M31 40 Q42 32 54 34" stroke="#ffffff" strokeWidth="2.5" strokeLinecap="round" fill="none" opacity="0.35" />

            {/* ears */}
            <circle cx="26" cy="56" r="3.5" fill="url(#mj-skin)" stroke="var(--border)" strokeWidth="1.5" />
            <circle cx="70" cy="56" r="3.5" fill="url(#mj-skin)" stroke="var(--border)" strokeWidth="1.5" />

            {/* face gloss (top-left highlight for a rounded, 3D feel) */}
            <ellipse cx="39" cy="45" rx="7" ry="4.5" fill="#ffffff" opacity="0.25" />

            {/* glasses */}
            <circle cx="39" cy="56" r="7" fill="none" stroke="var(--border)" strokeWidth="2" />
            <circle cx="57" cy="56" r="7" fill="none" stroke="var(--border)" strokeWidth="2" />
            <line x1="46" y1="56" x2="50" y2="56" stroke="var(--border)" strokeWidth="2" />

            {/* eyes (blink) */}
            <ellipse className="munimji-mascot-eye" cx="39" cy="56" rx="2.2" ry="2.2" fill="#1a1a1a" />
            <ellipse className="munimji-mascot-eye" cx="57" cy="56" rx="2.2" ry="2.2" fill="#1a1a1a" />

            {/* mustache */}
            <path d="M36 66 Q48 72 60 66 Q56 70 48 70 Q40 70 36 66 Z" fill="#3a2a1a" />

            {/* smile */}
            <path d="M42 69 Q48 73 54 69" stroke="#7a4a2a" strokeWidth="1.5" fill="none" strokeLinecap="round" />
          </svg>
        </div>
      </div>
    </div>
  );
}
