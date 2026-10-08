import { Link } from "react-router-dom";
import { COMPANY } from "./content";
import { Logo } from "./Decor";

export function LandingFooter() {
  return (
    <footer className="border-t border-forest-900/10 bg-sand-100">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-10 text-sm text-stone-600 sm:flex-row sm:items-center sm:px-6">
        <div className="flex items-center gap-3">
          <Logo className="h-7 w-7" />
          <span>
            <span className="font-display font-bold text-forest-900">CampBuddy</span> is built by {COMPANY.name}.
          </span>
        </div>
        <nav className="flex flex-wrap gap-x-6 gap-y-2 sm:ml-auto" aria-label="Footer">
          <a href={`mailto:${COMPANY.email}`} className="hover:text-forest-700">{COMPANY.email}</a>
          <Link to="/privacy" className="hover:text-forest-700">Privacy</Link>
          <Link to="/login" className="hover:text-forest-700">Log in</Link>
          <span className="text-stone-400">© {new Date().getFullYear()} {COMPANY.name}</span>
        </nav>
      </div>
    </footer>
  );
}
