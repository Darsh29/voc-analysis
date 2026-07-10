type Props = { text: string }

export default function KeyFindingsBox({ text }: Props) {
  return (
    <section className="px-6 py-2 md:px-10">
      <div className="rounded-lg border border-[var(--border)] border-l-4 border-l-[var(--teal)] bg-[var(--surface)] px-5 py-4">
        <h2 className="mb-1 text-xs font-medium uppercase tracking-wide text-[var(--text-dim)]">
          Key Findings
        </h2>
        <p className="text-sm leading-relaxed text-[var(--text)] md:text-base">{text}</p>
      </div>
    </section>
  )
}
