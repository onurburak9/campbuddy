import { Button } from "./Button";

interface Props {
  page: number;
  hasNext: boolean;
  onPrev: () => void;
  onNext: () => void;
}

export function Pagination({ page, hasNext, onPrev, onNext }: Props) {
  return (
    <div className="flex items-center justify-between pt-4">
      <Button variant="secondary" size="sm" disabled={page <= 1} onClick={onPrev}>
        ← Prev
      </Button>
      <span className="text-sm text-stone-500 dark:text-[#888]">Page {page}</span>
      <Button variant="secondary" size="sm" disabled={!hasNext} onClick={onNext}>
        Next →
      </Button>
    </div>
  );
}
