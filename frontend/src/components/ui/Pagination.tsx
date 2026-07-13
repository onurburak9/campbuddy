import { Button } from "./Button";

interface Props {
  page: number;
  hasNext: boolean;
  totalPages?: number;
  onPrev: () => void;
  onNext: () => void;
}

export function Pagination({ page, hasNext, totalPages, onPrev, onNext }: Props) {
  return (
    <div className="grid grid-cols-3 items-center pt-4">
      <Button
        variant="secondary"
        size="sm"
        className="justify-self-start"
        disabled={page <= 1}
        onClick={onPrev}
      >
        ← Prev
      </Button>
      <span className="justify-self-center text-sm text-stone-500 dark:text-[#888]">
        {totalPages != null ? `Page ${page} of ${totalPages}` : `Page ${page}`}
      </span>
      {hasNext && (
        <Button variant="secondary" size="sm" className="justify-self-end" onClick={onNext}>
          Next →
        </Button>
      )}
    </div>
  );
}
