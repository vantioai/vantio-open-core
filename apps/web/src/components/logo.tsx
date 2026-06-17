interface LogoProps {
  className?: string;
  size?: number;
}

/**
 * Inline SVG recreation of the Vantio mark: outer crosshair ring
 * (circle with 4 gaps at cardinal points) + inner ∅ symbol.
 * Renders white-on-transparent via currentColor — themes via CSS color.
 */
export function Logo({ className, size = 28 }: LogoProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 100 100"
      fill="none"
      width={size}
      height={size}
      aria-label="Vantio AI logo"
      className={className}
    >
      {/* Outer crosshair ring — 4 arcs with gaps at N/E/S/W */}
      <path stroke="currentColor" strokeWidth="7" strokeLinecap="butt"
        d="M 54.75 8.27 A 42 42 0 0 1 91.73 45.25"/>
      <path stroke="currentColor" strokeWidth="7" strokeLinecap="butt"
        d="M 91.73 54.75 A 42 42 0 0 1 54.75 91.73"/>
      <path stroke="currentColor" strokeWidth="7" strokeLinecap="butt"
        d="M 45.25 91.73 A 42 42 0 0 1 8.27 54.75"/>
      <path stroke="currentColor" strokeWidth="7" strokeLinecap="butt"
        d="M 8.27 45.25 A 42 42 0 0 1 45.25 8.27"/>
      {/* Inner ∅ mark */}
      <circle cx="50" cy="50" r="22" stroke="currentColor" strokeWidth="6"/>
      <line x1="31" y1="69" x2="69" y2="31" stroke="currentColor" strokeWidth="6" strokeLinecap="butt"/>
    </svg>
  );
}
