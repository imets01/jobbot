import { Plus, X } from "lucide-react";
import { useId, useState } from "react";

export function TagInput({
  label,
  values,
  onChange,
  suggestions = [],
  placeholder = "Type and press Enter",
}: {
  label: string;
  values: string[];
  onChange: (values: string[]) => void;
  suggestions?: string[];
  placeholder?: string;
}) {
  const [input, setInput] = useState("");
  const listId = useId();

  const add = (raw: string) => {
    const additions = raw.split(",").map((value) => value.trim()).filter(Boolean);
    if (!additions.length) return;
    const existing = new Set(values.map((value) => value.toLowerCase()));
    onChange([...values, ...additions.filter((value) => !existing.has(value.toLowerCase()))]);
    setInput("");
  };

  return (
    <label className="tag-field">
      {label}
      <div className="tag-input-shell">
        {values.map((value) => (
          <span className="form-tag" key={value}>
            {value}
            <button type="button" onClick={() => onChange(values.filter((item) => item !== value))} aria-label={`Remove ${value}`}>
              <X size={12} />
            </button>
          </span>
        ))}
        <input
          value={input}
          list={suggestions.length ? listId : undefined}
          onChange={(event) => setInput(event.target.value)}
          onBlur={() => input.trim() && add(input)}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === ",") {
              event.preventDefault();
              add(input);
            }
            if (event.key === "Backspace" && !input && values.length) {
              onChange(values.slice(0, -1));
            }
          }}
          placeholder={values.length ? "Add another…" : placeholder}
        />
        {suggestions.length > 0 && <datalist id={listId}>{suggestions.map((value) => <option key={value} value={value} />)}</datalist>}
      </div>
    </label>
  );
}

export function StringListField({
  label,
  values,
  onChange,
  placeholder,
  rows = 4,
}: {
  label: string;
  values: string[];
  onChange: (values: string[]) => void;
  placeholder: string;
  rows?: number;
}) {
  return (
    <label>
      {label}
      <textarea
        rows={rows}
        value={values.join("\n")}
        onChange={(event) => onChange(event.target.value.split("\n"))}
        placeholder={placeholder}
      />
      <small className="field-help">One entry per line</small>
    </label>
  );
}

export function CheckChoice({
  label,
  checked,
  onChange,
  description,
  disabled = false,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  description?: string;
  disabled?: boolean;
}) {
  return (
    <label className={`check-choice ${disabled ? "is-disabled" : ""}`}>
      <input type="checkbox" checked={checked} disabled={disabled} onChange={(event) => onChange(event.target.checked)} />
      <span>{label}{description && <small>{description}</small>}</span>
    </label>
  );
}

export function AddRowButton({ label, onClick }: { label: string; onClick: () => void }) {
  return <button type="button" className="text-link add-row-button" onClick={onClick}><Plus size={14} /> {label}</button>;
}
