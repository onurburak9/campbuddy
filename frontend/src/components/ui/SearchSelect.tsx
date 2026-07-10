import { useEffect, useState, type ReactNode } from "react";
import { Input } from "./Input";
import { Button } from "./Button";
import { Spinner } from "./Spinner";

interface Item {
  id: number;
  name: string;
}

interface SearchSelectProps<T extends Item> {
  label: string;
  selected: T[];
  onChange: (items: T[]) => void;
  search: (query: string) => Promise<T[]>;
  renderResult?: (item: T) => ReactNode;
  disabled?: boolean;
  placeholder?: string;
}

export function SearchSelect<T extends Item>({
  label,
  selected,
  onChange,
  search,
  renderResult,
  disabled,
  placeholder,
}: SearchSelectProps<T>) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<T[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [addById, setAddById] = useState("");

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([]);
      setError(null);
      return;
    }
    let cancelled = false;
    const timer = setTimeout(() => {
      setLoading(true);
      setError(null);
      search(query)
        .then((items) => {
          if (!cancelled) setResults(items);
        })
        .catch((err) => {
          if (!cancelled) setError(err instanceof Error ? err.message : "Search failed");
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query, search]);

  function select(item: T) {
    if (!selected.some((s) => s.id === item.id)) onChange([...selected, item]);
    setQuery("");
    setResults([]);
  }

  function remove(id: number) {
    onChange(selected.filter((s) => s.id !== id));
  }

  function addRawId() {
    const id = Number(addById.trim());
    if (!Number.isFinite(id) || id <= 0) return;
    if (!selected.some((s) => s.id === id)) {
      onChange([...selected, { id, name: `ID ${id}` } as T]);
    }
    setAddById("");
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {selected.map((item) => (
          <span key={item.id} className="inline-flex items-center gap-1 rounded-full bg-forest-100 px-2.5 py-1 text-sm text-forest-800 dark:bg-[#222] dark:text-[#EEE]">
            {item.name}
            <button type="button" aria-label={`Remove ${item.name}`} onClick={() => remove(item.id)}>
              ×
            </button>
          </span>
        ))}
      </div>
      <Input
        label={label}
        value={query}
        disabled={disabled}
        placeholder={placeholder}
        onChange={(e) => setQuery(e.target.value)}
      />
      {loading && <Spinner className="h-4 w-4" />}
      {error && <p className="text-sm text-[#DC2626]">{error}</p>}
      {!loading && !error && query.trim().length >= 2 && results.length === 0 && (
        <p className="text-sm text-stone-500 dark:text-[#888]">No matches — try a different search or add by ID.</p>
      )}
      {results.length > 0 && (
        <ul className="max-h-72 overflow-y-auto rounded-md border border-sand-200 dark:border-[#222]">
          {results.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                className="block w-full px-3 py-2.5 text-left text-sm hover:bg-sand-100 dark:hover:bg-[#222]"
                onClick={() => select(item)}
              >
                {renderResult ? renderResult(item) : item.name}
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex items-end gap-2">
        <Input
          label="Add by ID"
          value={addById}
          onChange={(e) => setAddById(e.target.value)}
          placeholder="e.g. 1074"
        />
        <Button type="button" variant="secondary" size="sm" onClick={addRawId}>
          Add
        </Button>
      </div>
    </div>
  );
}
