/** Indian digit grouping, e.g. 1234567 -> "₹12,34,567". Mirrors backend/app/money.py. */
export function formatInr(amount: number): string {
  const sign = amount < 0 ? "-" : "";
  const digits = Math.abs(Math.round(amount)).toString();

  let grouped: string;
  if (digits.length <= 3) {
    grouped = digits;
  } else {
    const last3 = digits.slice(-3);
    let rest = digits.slice(0, -3);
    const parts: string[] = [];
    while (rest.length > 2) {
      parts.unshift(rest.slice(-2));
      rest = rest.slice(0, -2);
    }
    if (rest) parts.unshift(rest);
    grouped = `${parts.join(",")},${last3}`;
  }

  return `${sign}₹${grouped}`;
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}
