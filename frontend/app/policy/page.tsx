import { Header } from "@/components/Header";
import { MarkdownTable } from "@/components/MarkdownTable";
import { api } from "@/lib/api";

export default async function PolicyPage() {
  const policy = await api.policy().catch(() => null);

  return (
    <div className="min-h-screen">
      <Header />
      <main className="mx-auto max-w-4xl px-6 py-8">
        <h1 className="mb-4 text-lg font-semibold">Policy</h1>
        {policy ? (
          <MarkdownTable markdown={policy.decision_table_markdown} />
        ) : (
          <p className="text-sm text-muted">Backend not reachable.</p>
        )}
      </main>
    </div>
  );
}
