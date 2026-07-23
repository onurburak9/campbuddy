import { useQuery } from "@tanstack/react-query";

interface Named {
  id: number;
  name: string;
}

/**
 * Resolves a plain list of numeric IDs (e.g. rec_area_ids/campground_ids/campsite_ids
 * on a Scan) to a Map<id, name> via the given resolve function. Names from
 * recreation.gov are stable, so results are cached indefinitely.
 *
 * Returns an empty map while loading or if resolution yields nothing, so
 * callers can fall back to displaying the raw ID.
 */
export function useResolvedNames(
  ids: number[],
  resolve: (ids: number[]) => Promise<Named[]>,
): Map<number, string> {
  const { data } = useQuery({
    queryKey: ["resolve-names", resolve.name, ids],
    queryFn: () => resolve(ids),
    enabled: ids.length > 0,
    staleTime: Infinity,
  });

  if (!data) return new Map();
  return new Map(data.map((item) => [item.id, item.name]));
}
