import { groupResults } from "../../lib/groupResults";
import { ResultCard } from "./ResultCard";
import { ResultGroupSection } from "./ResultGroupSection";
import type { ScanResult } from "../../types";

function counts(results: ScanResult[]) {
  const available = results.filter((r) => r.is_available).length;
  return { available, gone: results.length - available };
}

export function GroupedResultsView({ results }: { results: ScanResult[] }) {
  const { areas, other } = groupResults(results);

  return (
    <div className="space-y-3">
      {areas.map((area) => {
        const areaResults = area.campgrounds.flatMap((c) => c.results);
        const areaCounts = counts(areaResults);
        return (
          <ResultGroupSection
            key={area.recreationAreaId}
            title={area.recreationAreaName}
            availableCount={areaCounts.available}
            goneCount={areaCounts.gone}
            defaultOpen={areas.length === 1}
          >
            {area.campgrounds.map((cg) => {
              const cgCounts = counts(cg.results);
              return (
                <ResultGroupSection
                  key={cg.facilityId}
                  title={cg.facilityName}
                  availableCount={cgCounts.available}
                  goneCount={cgCounts.gone}
                  defaultOpen={area.campgrounds.length === 1}
                  indent
                >
                  {cg.results.map((r) => (
                    <ResultCard key={r.id} result={r} />
                  ))}
                </ResultGroupSection>
              );
            })}
          </ResultGroupSection>
        );
      })}
      {other.length > 0 && (
        <ResultGroupSection
          title="Other"
          subtitle="results without a resolved campground"
          availableCount={counts(other).available}
          goneCount={counts(other).gone}
          defaultOpen={areas.length === 0}
        >
          {other.map((r) => (
            <ResultCard key={r.id} result={r} />
          ))}
        </ResultGroupSection>
      )}
    </div>
  );
}
