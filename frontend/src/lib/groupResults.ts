import type { ScanResult } from "../types";

export interface CampgroundGroup {
  facilityId: string;
  facilityName: string;
  results: ScanResult[];
}

export interface AreaGroup {
  recreationAreaId: string;
  recreationAreaName: string;
  campgrounds: CampgroundGroup[];
}

export interface GroupedResults {
  areas: AreaGroup[];
  other: ScanResult[];
}

function isGroupable(r: ScanResult): boolean {
  return r.facility_id != null && r.recreation_area_id != null;
}

function mostRecentActivity(results: ScanResult[]): number {
  return Math.max(...results.map((r) => new Date(r.last_seen_at).getTime()));
}

export function groupResults(results: ScanResult[]): GroupedResults {
  const other: ScanResult[] = [];
  const areaOrder: string[] = [];
  const areas = new Map<string, { name: string; campgroundOrder: string[]; campgrounds: Map<string, CampgroundGroup> }>();

  for (const r of results) {
    if (!isGroupable(r)) {
      other.push(r);
      continue;
    }
    const areaId = r.recreation_area_id as string;
    const facilityId = r.facility_id as string;
    if (!areas.has(areaId)) {
      areas.set(areaId, { name: r.recreation_area ?? areaId, campgroundOrder: [], campgrounds: new Map() });
      areaOrder.push(areaId);
    }
    const area = areas.get(areaId)!;
    if (!area.campgrounds.has(facilityId)) {
      area.campgrounds.set(facilityId, { facilityId, facilityName: r.facility_name, results: [] });
      area.campgroundOrder.push(facilityId);
    }
    area.campgrounds.get(facilityId)!.results.push(r);
  }

  const areaGroups: AreaGroup[] = areaOrder.map((areaId) => {
    const area = areas.get(areaId)!;
    const campgrounds = area.campgroundOrder
      .map((id) => area.campgrounds.get(id)!)
      .sort((a, b) => mostRecentActivity(b.results) - mostRecentActivity(a.results));
    return { recreationAreaId: areaId, recreationAreaName: area.name, campgrounds };
  });

  areaGroups.sort((a, b) => {
    const aResults = a.campgrounds.flatMap((c) => c.results);
    const bResults = b.campgrounds.flatMap((c) => c.results);
    return mostRecentActivity(bResults) - mostRecentActivity(aResults);
  });

  return { areas: areaGroups, other };
}

export function hasGroupableResults(results: ScanResult[]): boolean {
  return results.some(isGroupable);
}
