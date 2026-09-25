import Link from "next/link";

const NAV = [
  { href: "/", label: "Home" },
  { href: "/invoices", label: "Invoices" },
  { href: "/clients", label: "Clients" },
  { href: "/policy", label: "Policy" },
  { href: "/audit", label: "Audit" },
];

export function Header() {
  return (
    <header className="flex flex-wrap items-center justify-between gap-4 border-b border-border px-6 py-4">
      <div className="flex items-baseline gap-3">
        <span className="text-xl font-semibold text-saffron">MunimJi</span>
        <span className="text-sm text-muted">Autonomous FinOps · Governed by Swytchcode</span>
      </div>
      <nav className="flex gap-4 text-sm">
        {NAV.map((item) => (
          <Link key={item.href} href={item.href} className="text-muted hover:text-foreground">
            {item.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
