import { driver } from "driver.js";
import "driver.js/dist/driver.css";
import "../styles/tour.css";

const WELCOME_SEEN_KEY = "campbuddy:tour-seen:welcome";
const WIZARD_SEEN_KEY = "campbuddy:tour-seen:wizard";
const WIZARD_DATES_SEEN_KEY = "campbuddy:tour-seen:wizard-dates";

export function hasSeenWelcomeTour(): boolean {
  return localStorage.getItem(WELCOME_SEEN_KEY) === "1";
}

export function hasSeenWizardTour(): boolean {
  return localStorage.getItem(WIZARD_SEEN_KEY) === "1";
}

export function hasSeenWizardDatesTour(): boolean {
  return localStorage.getItem(WIZARD_DATES_SEEN_KEY) === "1";
}

export function startWelcomeTour(): () => void {
  const instance = driver({
    showProgress: true,
    onDestroyed: () => localStorage.setItem(WELCOME_SEEN_KEY, "1"),
    steps: [
      {
        element: '[data-tour="scans-list"]',
        popover: {
          title: "Your scans",
          description: "Your scans will show up here once you create one.",
        },
      },
      {
        element: '[data-tour="new-scan-button"]',
        popover: {
          title: "Create a scan",
          description: "Click here to start monitoring a campground for availability.",
        },
      },
      {
        element: '[data-tour="settings-link"]',
        popover: {
          title: "Settings",
          description: "Set up email/Telegram notifications and your Recreation.gov credentials here.",
        },
      },
    ],
  });
  instance.drive();
  return () => instance.destroy();
}

export function startWizardProviderTour(): () => void {
  const instance = driver({
    showProgress: true,
    onDestroyed: () => localStorage.setItem(WIZARD_SEEN_KEY, "1"),
    steps: [
      {
        element: '[data-tour="provider-select"]',
        popover: {
          title: "Provider",
          description: "Only RecreationDotGov is available today — other providers are coming soon.",
        },
      },
      {
        element: '[data-tour="search-recreation-areas"]',
        popover: {
          title: "Find a Recreation Area",
          description:
            "Search by name, or if you already know the numeric ID from the Recreation.gov URL " +
            "(e.g. recreation.gov/camping/campgrounds/2991), paste it into \"Add by ID\" below.",
        },
      },
      {
        element: '[data-tour="narrow-campground-campsite"]',
        popover: {
          title: "Narrow it down (optional)",
          description:
            "Optional, and independent of the Recreation Area above — set a Campground or " +
            "Campsite ID on their own, or combine them. A Recreation Area, a Campground, and a " +
            "Campsite ID all work on their own; you don't need to pick one before the others.",
        },
      },
    ],
  });
  instance.drive();
  return () => instance.destroy();
}

export function startWizardDatesTour(): () => void {
  const instance = driver({
    showProgress: true,
    onDestroyed: () => localStorage.setItem(WIZARD_DATES_SEEN_KEY, "1"),
    steps: [
      {
        element: '[data-tour="quick-picks"]',
        popover: {
          title: "Quick picks",
          description:
            "Shortcuts for the usual trips, so you don't have to work out dates by hand. " +
            "Each one replaces everything below it — the search ranges, the nights, the " +
            "days-of-week and the weekends-only switch — rather than merging with what's " +
            "already there. Everything stays editable afterwards.",
        },
      },
      {
        element: '[data-tour="search-summary"]',
        popover: {
          title: "What you'll actually be searching",
          description:
            "This line always describes the current settings in plain English, so you can " +
            "check it matches what you meant. It counts nights, so it ends on the last night " +
            "you could stay - which is a day before \"Search until\", the day you'd check out.",
        },
      },
      {
        element: '[data-tour="nights-field"]',
        popover: {
          title: "Nights is an exact length",
          description:
            "CampBuddy only alerts you about stays of exactly this many consecutive nights, " +
            "so 2 will not match a single free night. Quick picks reset it: the weekend picks " +
            "set 2 for a Fri-Sun trip, while the single-night and whole-month picks set 1. " +
            "Change it afterwards and the summary above updates.",
        },
      },
    ],
  });
  instance.drive();
  return () => instance.destroy();
}
