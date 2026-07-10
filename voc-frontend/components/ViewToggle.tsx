export type ViewMode = 'executive' | 'full'

type Props = {
  mode: ViewMode
  onChange: (mode: ViewMode) => void
}

export default function ViewToggle({ mode, onChange }: Props) {
  return (
    <div className="inline-flex rounded-lg border border-[var(--border)] bg-[var(--surface)] p-1">
      {(
        [
          { key: 'executive', label: 'Executive Summary' },
          { key: 'full', label: 'Full Detail' },
        ] as const
      ).map((opt) => (
        <button
          key={opt.key}
          type="button"
          onClick={() => onChange(opt.key)}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
            mode === opt.key
              ? 'bg-[var(--border)] text-[var(--text)]'
              : 'text-[var(--text-dim)] hover:text-[var(--text)]'
          }`}
          aria-pressed={mode === opt.key}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}
