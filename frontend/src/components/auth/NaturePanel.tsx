export function NaturePanel() {
  return (
    <div className="relative hidden flex-col justify-end overflow-hidden bg-gradient-to-br from-forest-800 via-forest-600 to-forest-500 p-12 text-white md:flex">
      <div className="absolute right-10 top-10 h-1 w-1 rounded-full bg-white/60" />
      <div className="absolute right-24 top-20 h-1 w-1 rounded-full bg-white/40" />
      <div className="absolute left-16 top-16 h-1 w-1 rounded-full bg-white/50" />
      <div className="mb-6 flex h-14 w-14 items-center justify-center rounded-2xl bg-white/15 backdrop-blur">
        <span className="text-3xl" aria-hidden>⛺</span>
      </div>
      <h2 className="text-3xl font-bold">CampBuddy</h2>
      <p className="mt-2 text-white/80">Never miss a campsite again</p>
      <svg className="pointer-events-none absolute bottom-0 left-0 w-full text-forest-900/40"
        viewBox="0 0 400 80" preserveAspectRatio="none" aria-hidden>
        <polygon points="40,80 60,30 80,80" fill="currentColor" />
        <polygon points="120,80 150,15 180,80" fill="currentColor" />
        <polygon points="240,80 270,25 300,80" fill="currentColor" />
        <polygon points="330,80 350,35 370,80" fill="currentColor" />
      </svg>
    </div>
  );
}
