import { fetchApi } from "./client";

export interface RecreationAreaResult {
  id: number;
  name: string;
  state: string | null;
}

export interface CampgroundResult {
  id: number;
  name: string;
  recreation_area: string;
  recreation_area_id: number;
}

export interface CampsiteResult {
  id: number;
  name: string;
  loop: string;
  campground_id: number;
}

function toParams(params: Record<string, string | number[] | undefined | null>): string {
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value == null) continue;
    if (Array.isArray(value)) value.forEach((v) => qs.append(key, String(v)));
    else qs.append(key, String(value));
  }
  return qs.toString();
}

export const search = {
  recreationAreas: (q: string) =>
    fetchApi<RecreationAreaResult[]>(`/search/recreation-areas?${toParams({ q })}`),
  resolveRecreationAreas: (ids: number[]) =>
    fetchApi<RecreationAreaResult[]>(`/search/recreation-areas/resolve?${toParams({ ids })}`),
  campgrounds: (q: string | null, recAreaIds: number[] | null) =>
    fetchApi<CampgroundResult[]>(`/search/campgrounds?${toParams({ q, rec_area_ids: recAreaIds })}`),
  resolveCampgrounds: (ids: number[]) =>
    fetchApi<CampgroundResult[]>(`/search/campgrounds/resolve?${toParams({ ids })}`),
  campsites: (campgroundIds: number[]) =>
    fetchApi<CampsiteResult[]>(`/search/campsites?${toParams({ campground_ids: campgroundIds })}`),
  resolveCampsites: (ids: number[]) =>
    fetchApi<CampsiteResult[]>(`/search/campsites/resolve?${toParams({ ids })}`),
};
