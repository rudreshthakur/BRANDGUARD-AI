export function Logo({ light = false }: { light?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <svg width="26" height="26" viewBox="0 0 32 32" aria-hidden>
        <rect width="32" height="32" rx="7" fill={light ? "#ffffff" : "#16213A"} />
        <path d="M10 8v16" stroke={light ? "#16213A" : "#fff"} strokeWidth="2.6" strokeLinecap="round" />
        <path d="M10 9h7a4 4 0 0 1 0 8h-7" fill="none" stroke={light ? "#16213A" : "#fff"} strokeWidth="2.6" />
        <path d="M10 17h8.5a4 4 0 0 1 0 8H10" fill="none" stroke="#2949C6" strokeWidth="2.6" />
      </svg>
      <span className={`text-[17px] font-semibold tracking-tight ${light ? "text-white" : "text-ink"}`}>BrandGuard</span>
    </span>
  );
}
