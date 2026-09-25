/** Minimal renderer for the specific pipe-table + heading shape produced by
 * backend/app/policy/explain.py. Not a general markdown parser. */
export function MarkdownTable({ markdown }: { markdown: string }) {
  const lines = markdown.split("\n");
  const blocks: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (line.startsWith("# ")) {
      blocks.push(
        <h1 key={i} className="mb-2 text-lg font-semibold">
          {line.slice(2)}
        </h1>
      );
      i++;
    } else if (line.startsWith("## ")) {
      blocks.push(
        <h2 key={i} className="mb-2 mt-6 text-sm font-semibold text-foreground">
          {line.slice(3)}
        </h2>
      );
      i++;
    } else if (line.startsWith("| ")) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i].startsWith("|")) {
        const cells = lines[i]
          .split("|")
          .slice(1, -1)
          .map((c) => c.trim());
        if (!cells.every((c) => /^-+$/.test(c))) rows.push(cells);
        i++;
      }
      const [header, ...body] = rows;
      blocks.push(
        <div key={i} className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs uppercase text-muted">
                {header.map((h, idx) => (
                  <th key={idx} className="px-3 py-2">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {body.map((row, rIdx) => (
                <tr key={rIdx} className="border-b border-border/60 font-mono text-xs last:border-0">
                  {row.map((cell, cIdx) => (
                    <td key={cIdx} className="px-3 py-2">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    } else if (line.startsWith("- ")) {
      const items: string[] = [];
      while (i < lines.length && lines[i].startsWith("- ")) {
        items.push(lines[i].slice(2));
        i++;
      }
      blocks.push(
        <ul key={i} className="list-inside list-disc space-y-1 text-sm text-muted">
          {items.map((item, idx) => (
            <li key={idx}>{item}</li>
          ))}
        </ul>
      );
    } else {
      i++;
    }
  }

  return <div className="flex flex-col gap-3">{blocks}</div>;
}
