import { describe, it, expect, vi, beforeEach } from "vitest";

const { driveMock, destroyMock, driverMock } = vi.hoisted(() => {
  const driveMock = vi.fn();
  const destroyMock = vi.fn();
  const driverMock = vi.fn((_config: any) => ({ drive: driveMock, destroy: destroyMock }));
  return { driveMock, destroyMock, driverMock };
});

vi.mock("driver.js", () => ({ driver: driverMock }));

import {
  startWelcomeTour,
  hasSeenWelcomeTour,
  startWizardProviderTour,
  hasSeenWizardTour,
} from "./tour";

describe("tour", () => {
  beforeEach(() => {
    localStorage.clear();
    driverMock.mockClear();
    driveMock.mockClear();
    destroyMock.mockClear();
  });

  it("returns a stop function that destroys the driver instance", () => {
    const stop = startWelcomeTour();
    expect(destroyMock).not.toHaveBeenCalled();
    stop();
    expect(destroyMock).toHaveBeenCalledTimes(1);
  });

  describe("welcome tour", () => {
    it("targets the 3 welcome-screen data-tour selectors in order", () => {
      startWelcomeTour();
      const config = driverMock.mock.calls[0][0];
      expect(config.steps.map((s: any) => s.element)).toEqual([
        '[data-tour="scans-list"]',
        '[data-tour="new-scan-button"]',
        '[data-tour="settings-link"]',
      ]);
      expect(driveMock).toHaveBeenCalledTimes(1);
    });

    it("has not been seen until the tour is destroyed", () => {
      expect(hasSeenWelcomeTour()).toBe(false);
      startWelcomeTour();
      expect(hasSeenWelcomeTour()).toBe(false);
      const config = driverMock.mock.calls[0][0];
      config.onDestroyed();
      expect(hasSeenWelcomeTour()).toBe(true);
    });
  });

  describe("wizard provider tour", () => {
    it("targets the 3 wizard data-tour selectors in order", () => {
      startWizardProviderTour();
      const config = driverMock.mock.calls[0][0];
      expect(config.steps.map((s: any) => s.element)).toEqual([
        '[data-tour="provider-select"]',
        '[data-tour="search-recreation-areas"]',
        '[data-tour="narrow-campground-campsite"]',
      ]);
      expect(driveMock).toHaveBeenCalledTimes(1);
    });

    it("has not been seen until the tour is destroyed", () => {
      expect(hasSeenWizardTour()).toBe(false);
      startWizardProviderTour();
      expect(hasSeenWizardTour()).toBe(false);
      const config = driverMock.mock.calls[0][0];
      config.onDestroyed();
      expect(hasSeenWizardTour()).toBe(true);
    });
  });
});
