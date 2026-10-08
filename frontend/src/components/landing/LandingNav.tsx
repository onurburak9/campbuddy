import { Link } from "react-router-dom";
import { Logo } from "./Decor";

const LINKS = [
  { href: "#how-it-works", label: "How it works" },
  { href: "#roadmap", label: "Roadmap" },
  { href: "#faq", label: "FAQ" },
];

export function LandingNav() {
  return (
    <header className="sticky top-0 z-30 border-b border-forest-900/5 bg-sand-50/80 backdrop-blur-md">
      <nav className="mx-auto flex h-16 max-w-6xl items-center gap-4 sm:gap-6 px-4 sm:px-6" aria-label="Main">
        <a href="#top" className="flex items-center gap-2 font-display text-lg font-extrabold text-forest-900">
          <Logo className="h-8 w-8" />
          CampBuddy
        </a>
        <div className="hidden items-center gap-6 text-sm font-medium text-stone-600 md:flex">
          {LINKS.map((l) => (
            <a key={l.href} href={l.href} className="transition-colors hover:text-forest-700">
              {l.label}
            </a>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-2">
          <Link to="/login" className="whitespace-nowrap rounded-lg px-3 py-2 text-sm font-semibold text-forest-800 transition-colors hover:bg-forest-50">
            Log in
          </Link>
          <Link
            to="/register"
            className="whitespace-nowrap rounded-lg bg-forest-700 px-3 py-2 sm:px-4 text-sm font-semibold text-white shadow-sm transition-all hover:-translate-y-0.5 hover:bg-forest-800"
          >
            Start a scan
          </Link>
        </div>
      </nav>
    </header>
  );
}
