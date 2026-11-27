import { ICONS } from "./icons";

export type IconName = keyof typeof ICONS;

export function Icon({ name, className = "" }: { name: IconName; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" width={18} height={18} fill="currentColor" aria-hidden className={`shrink-0 ${className}`}>
      {ICONS[name]}
    </svg>
  );
}

export function PageHeader({ title, children }: { title: React.ReactNode; children?: React.ReactNode }) {
  return (
    <header className="sticky top-14 md:top-0 z-[5] min-h-12 px-4 md:px-6 py-2 bg-white border-b md:rounded-tl-[16px] flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
      <h1 className="text-xl font-semibold tracking-tight min-w-0 truncate">{title}</h1>
      {children && <div className="flex items-center gap-2">{children}</div>}
    </header>
  );
}

// Доля совпадений: заполненное кольцо, цвет меняется по порогам отчёта
export function Ring({ value }: { value: number }) {
  const c = 2 * Math.PI * 6;
  const color = value >= 50 ? "#dc2626" : value >= 20 ? "#d08700" : "#17935a";
  return (
    <svg width={16} height={16} viewBox="0 0 16 16" aria-hidden className="shrink-0 -rotate-90">
      <circle cx={8} cy={8} r={6} fill="none" stroke="#e6e6e9" strokeWidth={2.5} />
      <circle
        cx={8}
        cy={8}
        r={6}
        fill="none"
        stroke={color}
        strokeWidth={2.5}
        strokeDasharray={`${(Math.min(100, value) / 100) * c} ${c}`}
      />
    </svg>
  );
}

export function Stats({ items }: { items: { label: string; value: React.ReactNode; note?: React.ReactNode }[] }) {
  return (
    <dl
      className={`grid gap-px bg-gray-200 border-b tabular ${
        items.length === 3 ? "grid-cols-1 sm:grid-cols-3" : "grid-cols-2 lg:grid-cols-4"
      }`}
    >
      {items.map((it) => (
        <div key={it.label} className="bg-white px-4 md:px-6 py-4">
          <dt className="text-xs text-gray-500">{it.label}</dt>
          <dd className="mt-1.5 text-2xl font-semibold tracking-tight">{it.value}</dd>
          {it.note && <dd className="mt-0.5 text-xs text-gray-500">{it.note}</dd>}
        </div>
      ))}
    </dl>
  );
}

const TONES = {
  green: "bg-green-600",
  amber: "bg-amber-500",
  red: "bg-red-600",
  blue: "bg-blue-500",
  gray: "bg-gray-300",
};

export type Tone = keyof typeof TONES;

export function Status({ tone = "gray", children }: { tone?: Tone; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-2 text-xs text-gray-700 whitespace-nowrap">
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${TONES[tone]}`} />
      {children}
    </span>
  );
}

export function Notice({ kind, children, onClose }: { kind: "ok" | "err"; children: React.ReactNode; onClose?: () => void }) {
  return (
    <div
      role={kind === "err" ? "alert" : "status"}
      className={`mx-4 md:mx-6 my-4 px-4 py-3 rounded-lg border flex items-start gap-3 break-all ${
        kind === "ok" ? "bg-gray-50 text-gray-800" : "bg-red-50 border-red-200 text-red-700"
      }`}
    >
      <span className="flex-1">{children}</span>
      {onClose && (
        <button type="button" onClick={onClose} aria-label="Закрыть" className="opacity-60 hover:opacity-100">
          <Icon name="close" />
        </button>
      )}
    </div>
  );
}

export function Similarity({ value }: { value: number | null }) {
  if (value == null) return <span className="text-gray-300">—</span>;
  const color = value >= 50 ? "text-red-700 font-medium" : value >= 20 ? "text-amber-700" : "text-green-700";
  return (
    <span className={`inline-flex items-center gap-2 ${color}`}>
      <Ring value={value} />
      {value.toFixed(1)}%
    </span>
  );
}

export function Tabs<T extends string>({ value, onChange, options }: { value: T; onChange: (v: T) => void; options: [T, string][] }) {
  return (
    <div className="flex gap-6 px-4 md:px-6 border-b overflow-x-auto">
      {options.map(([key, label]) => (
        <button
          key={key}
          type="button"
          onClick={() => onChange(key)}
          aria-pressed={value === key}
          className={`h-10 -mb-px shrink-0 text-sm font-medium border-b-2 transition-colors ${
            value === key ? "border-gray-900 text-gray-900" : "border-transparent text-gray-500 hover:text-gray-900"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

export function Logo({ className = "h-6" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <span
        className="inline-flex items-center justify-center rounded-[4px] bg-teal-700 text-white shrink-0"
        style={{ width: "1.1em", height: "1.1em" }}
        aria-hidden
      >
        <svg viewBox="0 0 16 16" className="w-[70%] h-[70%]" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M3.5 8.2 6.4 11l6-7" />
        </svg>
      </span>
      <span className="font-semibold tracking-tight text-gray-900 text-[1.05em] leading-none">Markly</span>
    </span>
  );
}
