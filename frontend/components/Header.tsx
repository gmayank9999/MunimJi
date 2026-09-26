import Link from "next/link";
import { ThemeToggle } from "./ThemeToggle";

const NAV = [
  { href: "/", label: "Home" },
  { href: "/invoices", label: "Invoices" },
  { href: "/clients", label: "Clients" },
  { href: "/approvals", label: "Approvals" },
  { href: "/policy", label: "Policy" },
  { href: "/audit", label: "Audit" },
];

export function Header() {
  return (
    <header className="sticky top-0 z-30 flex flex-wrap items-center justify-between gap-4 border-b border-border bg-background/85 px-6 py-4 backdrop-blur">
      <div className="flex items-baseline gap-3">
        <span className="text-xl font-semibold tracking-tight text-saffron">MunimJi</span>
        <span className="hidden text-sm text-muted sm:inline">
          Autonomous FinOps · Governed by Swytchcode
        </span>
      </div>
      <div className="flex items-center gap-5">
        <nav className="flex gap-4 text-sm">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="text-muted transition-colors hover:text-foreground"
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <ThemeToggle />
      </div>
    </header>
  );
}
