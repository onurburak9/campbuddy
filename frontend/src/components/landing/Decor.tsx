import { cn } from "../../lib/cn";

/** Deterministic wobbly closed ring around (cx, cy) — one topographic contour line. */
function contour(cx: number, cy: number, r: number, seed: number): string {
  const steps = 48;
  const pts: string[] = [];
  for (let i = 0; i <= steps; i++) {
    const t = (i / steps) * Math.PI * 2;
    const wobble =
      1 + 0.12 * Math.sin(3 * t + seed) + 0.07 * Math.sin(5 * t + seed * 1.7) + 0.04 * Math.sin(9 * t + seed * 0.3);
    const x = cx + Math.cos(t) * r * wobble * 1.25;
    const y = cy + Math.sin(t) * r * wobble;
    pts.push(`${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`);
  }
  return pts.join(" ") + "Z";
}

const PEAKS = [
  { cx: 180, cy: 160, rings: 9, seed: 1.3 },
  { cx: 920, cy: 420, rings: 11, seed: 4.1 },
  { cx: 560, cy: 720, rings: 7, seed: 2.6 },
];

/** Topographic map texture used behind sections. Purely decorative. */
export function Topo({ className }: { className?: string }) {
  return (
    <svg
      className={cn("pointer-events-none absolute inset-0 h-full w-full", className)}
      viewBox="0 0 1200 800"
      preserveAspectRatio="xMidYMid slice"
      aria-hidden
    >
      <g fill="none" stroke="currentColor" strokeWidth="1.2">
        {PEAKS.flatMap((p) =>
          Array.from({ length: p.rings }, (_, i) => (
            <path key={`${p.cx}-${i}`} d={contour(p.cx, p.cy, 24 + i * 34, p.seed + i * 0.25)} />
          )),
        )}
      </g>
    </svg>
  );
}

export function Logo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <rect width="32" height="32" rx="8" fill="#2E6F40" />
      <path d="M16 7 L26 25 H6 Z" fill="#FAF9F6" />
      <path d="M16 13 L21 25 H11 Z" fill="#2E6F40" />
    </svg>
  );
}

/** Shared ring frame for the How-it-works merit badges. */
function BadgeFrame({ id, ring, children }: { id: string; ring: string; children: React.ReactNode }) {
  return (
    <svg viewBox="0 0 120 120" className="h-28 w-28 drop-shadow-sm transition-transform duration-300 group-hover:-rotate-6 group-hover:scale-105" aria-hidden>
      <defs>
        <clipPath id={`badge-clip-${id}`}>
          <circle cx="60" cy="60" r="46" />
        </clipPath>
      </defs>
      <circle cx="60" cy="60" r="58" fill={ring} />
      <circle cx="60" cy="60" r="52" fill="none" stroke="#FAF9F6" strokeWidth="2" strokeDasharray="3 5" opacity="0.7" />
      <g clipPath={`url(#badge-clip-${id})`}>{children}</g>
      <circle cx="60" cy="60" r="46" fill="none" stroke="#13301F" strokeWidth="2.5" opacity="0.35" />
    </svg>
  );
}

export function StepBadge({ kind }: { kind: "pin" | "radar" | "ping" | "tent" }) {
  switch (kind) {
    case "pin":
      return (
        <BadgeFrame id={kind} ring="#E0C48A">
          <rect width="120" height="120" fill="#BFE0E6" />
          <path d="M0 92 L30 58 L48 76 L72 44 L120 96 V120 H0Z" fill="#4A8C61" />
          <path d="M60 52 L72 44 L80 53 L70 50 L64 56Z" fill="#FAF9F6" />
          <path d="M0 104 Q60 88 120 104 V120 H0Z" fill="#235732" />
          <path d="M60 26 a12 12 0 0 1 12 12 c0 9 -12 22 -12 22 s-12 -13 -12 -22 a12 12 0 0 1 12 -12z" fill="#C7522A" />
          <circle cx="60" cy="38" r="4.5" fill="#FAF9F6" />
        </BadgeFrame>
      );
    case "radar":
      return (
        <BadgeFrame id={kind} ring="#9BB7A0">
          <rect width="120" height="120" fill="#141C36" />
          <circle cx="60" cy="74" r="40" fill="none" stroke="#74AC86" strokeWidth="1" opacity="0.5" />
          <circle cx="60" cy="74" r="26" fill="none" stroke="#74AC86" strokeWidth="1" opacity="0.5" />
          <g className="origin-[60px_74px] motion-safe:animate-sweep">
            <path d="M60 74 L60 30 A44 44 0 0 1 98 52Z" fill="#74AC86" opacity="0.5" />
          </g>
          <circle cx="82" cy="58" r="3.5" fill="#E0855F" className="motion-safe:animate-twinkle" />
          {[20, 34, 86, 100].map((x, i) => (
            <path key={x} d={`M${x} 110 L${x + 9} ${84 - (i % 2) * 8} L${x + 18} 110Z`} fill="#235732" />
          ))}
          <circle cx="24" cy="24" r="1.2" fill="#fff" />
          <circle cx="96" cy="30" r="1" fill="#fff" />
        </BadgeFrame>
      );
    case "ping":
      return (
        <BadgeFrame id={kind} ring="#EBAD93">
          <rect width="120" height="120" fill="#F6D6C8" />
          <rect x="40" y="24" width="40" height="76" rx="8" fill="#1B4332" />
          <rect x="44" y="32" width="32" height="58" rx="3" fill="#FAF9F6" />
          <rect x="47" y="38" width="26" height="14" rx="3" fill="#357A4B" />
          <rect x="47" y="56" width="18" height="4" rx="2" fill="#DFDCD9" />
          <rect x="47" y="63" width="22" height="4" rx="2" fill="#DFDCD9" />
          <circle cx="82" cy="30" r="10" fill="#C7522A" />
          <text x="82" y="34.5" textAnchor="middle" fontSize="13" fontWeight="700" fill="#fff" fontFamily="sans-serif">!</text>
          <path d="M92 44 q6 6 0 12 M98 40 q10 10 0 20" stroke="#C7522A" strokeWidth="2.5" fill="none" strokeLinecap="round" />
        </BadgeFrame>
      );
    case "tent":
      return (
        <BadgeFrame id={kind} ring="#7E8BC4">
          <rect width="120" height="120" fill="#1E2A4A" />
          {[[22, 28], [40, 18], [88, 22], [100, 40], [70, 14]].map(([x, y]) => (
            <circle key={`${x}-${y}`} cx={x} cy={y} r="1.3" fill="#fff" className="motion-safe:animate-twinkle" />
          ))}
          <path d="M0 92 Q60 80 120 92 V120 H0Z" fill="#141C36" />
          <path d="M60 42 L90 92 H30Z" fill="#D66A40" />
          <path d="M60 58 L72 92 H48Z" fill="#F2C14E" />
          <circle cx="88" cy="44" r="11" fill="#357A4B" />
          <path d="M83 44 l4 4 l7 -8" stroke="#fff" strokeWidth="3" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        </BadgeFrame>
      );
  }
}

const ICON_PATHS: Record<string, string> = {
  cart: "M3 4h2l2.4 10.2a1 1 0 0 0 1 .8h8.9a1 1 0 0 0 1-.8L20 8H6.2 M9 20a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z M17 20a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z",
  calendar: "M4 6h16v14H4z M4 10h16 M8 3v4 M16 3v4 M8 14h2 M14 14h2",
  gear: "M3 20 L12 5 L21 20Z M12 20 L12 13 M9 20 L12 13 L15 20",
  bell: "M6 16V11a6 6 0 1 1 12 0v5l2 2H4z M10 21h4",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z M12 7v5l3 2",
  chart: "M4 20V4 M4 20h16 M8 16v-4 M12 16V8 M16 16v-6",
};

export function FeatureIcon({ name }: { name: string }) {
  return (
    <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d={ICON_PATHS[name]} />
    </svg>
  );
}
