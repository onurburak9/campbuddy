import { driver } from "driver.js";
import "driver.js/dist/driver.css";
import "../styles/tour.css";

const WELCOME_SEEN_KEY = "campbuddy:tour-seen:welcome";
const WIZARD_SEEN_KEY = "campbuddy:tour-seen:wizard";

export function hasSeenWelcomeTour(): boolean {
  return localStorage.getItem(WELCOME_SEEN_KEY) === "1";
}

export function hasSeenWizardTour(): boolean {
  return localStorage.getItem(WIZARD_SEEN_KEY) === "1";
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
            "Optionally narrow down to a specific campground or campsite once you've picked a " +
            "Recreation Area — leave these blank to monitor the whole Recreation Area.",
        },
      },
    ],
  });
  instance.drive();
  return () => instance.destroy();
}
