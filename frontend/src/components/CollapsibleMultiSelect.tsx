import { useEffect, useRef, useState } from "react";

interface Option {
  value: string;
  label: string;
}

interface CollapsibleMultiSelectProps {
  options: Option[];
  selected: string[];
  onChange: (values: string[]) => void;
  placeholder?: string;
}

export function CollapsibleMultiSelect({ options, selected, onChange, placeholder = "Select..." }: CollapsibleMultiSelectProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  function toggle(value: string) {
    if (selected.includes(value)) {
      onChange(selected.filter((v) => v !== value));
    } else {
      onChange([...selected, value]);
    }
  }

  const selectedLabels = selected
    .map((v) => options.find((o) => o.value === v)?.label ?? v)
    .join(", ");

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        className="panel-field w-full cursor-pointer text-left"
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
      >
        <span className="block truncate text-sm text-[var(--text-primary)]">
          {selected.length > 0 ? selectedLabels : <span className="text-[var(--text-disabled)]">{placeholder}</span>}
        </span>
        <span className="pointer-events-none ml-auto shrink-0 text-[var(--text-disabled)]">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="absolute z-20 mt-1 w-full rounded border border-[var(--border)] bg-[var(--surface)] shadow-lg">
          {options.length === 0 ? (
            <p className="px-3 py-2 text-sm text-[var(--text-disabled)]">No options available</p>
          ) : (
            <ul className="max-h-56 overflow-y-auto py-1">
              {options.map((option) => {
                const checked = selected.includes(option.value);
                return (
                  <li key={option.value}>
                    <label className="flex cursor-pointer items-center gap-2 px-3 py-2 text-sm hover:bg-[var(--surface-hover)]">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggle(option.value)}
                        className="h-4 w-4 shrink-0"
                      />
                      <span className="truncate text-[var(--text-primary)]">{option.label}</span>
                    </label>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
