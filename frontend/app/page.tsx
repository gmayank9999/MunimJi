import { Header } from "@/components/Header";
import { RunConsole } from "@/components/RunConsole";
import { api } from "@/lib/api";

export default async function Home() {
  const kpis = await api.kpis().catch(() => null);

  return (
    <div className="min-h-screen">
      <Header />
      <main className="mx-auto flex max-w-6xl flex-col gap-6 px-6 py-8">
        <RunConsole initialKpis={kpis} />
      </main>
    </div>
  );
}
