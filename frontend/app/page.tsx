"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { TeamCard } from "@/lib/types";
import { raceColor } from "@/lib/api";
import { Banner, BigButton, PinPad } from "@/components/ui";

export default function LoginPage() {
  const router = useRouter();
  const [teams, setTeams] = useState<TeamCard[]>([]);
  const [teamId, setTeamId] = useState<number | null>(null);
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (window.localStorage.getItem("bb_token")) {
      router.replace("/dashboard");
      return;
    }
    api<TeamCard[]>("/api/teams")
      .then(setTeams)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [router]);

  async function enter(nextPin = pin) {
    if (!teamId || nextPin.length !== 4 || busy) return;
    setBusy(true);
    setError("");
    try {
      const result = await api<{ token: string }>("/api/auth/login", {
        body: { team_id: teamId, pin: nextPin },
        token: null,
      });
      window.localStorage.setItem("bb_token", result.token);
      router.push("/dashboard");
    } catch (err) {
      setPin("");
      setError(err instanceof Error ? err.message : "PIN incorrecto.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto min-h-screen w-full max-w-md px-4 pb-10 pt-8">
      <div className="mb-6 text-center">
        <div className="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-full border-2 border-gold bg-card shadow-[0_0_0_8px_rgba(240,193,77,0.08)]">
          <span className="font-display text-2xl text-gold">BB</span>
        </div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-gold">Blood Bowl 2020</p>
        <h1 className="mt-1 font-display text-4xl uppercase leading-none text-bone">Liga de la Mesa</h1>
        <p className="mt-2 text-sm text-muted">Elige tu equipo e introduce el PIN de cuatro cifras.</p>
      </div>
      {error && <Banner>{error}</Banner>}
      {loading ? (
        <p className="text-center text-muted">Cargando equipos…</p>
      ) : (
        <div className="space-y-2">
          {teams.map((team) => {
            const selected = team.id === teamId;
            return (
              <button
                key={team.id}
                type="button"
                onClick={() => {
                  setTeamId(team.id);
                  setPin("");
                  setError("");
                }}
                className={`flex w-full items-center gap-3 rounded-2xl border px-3 py-3 text-left ${
                  selected ? "border-gold bg-card2" : "border-line bg-card"
                }`}
              >
                <span className="h-10 w-1.5 rounded-full" style={{ background: raceColor(team.race_key) }} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-display text-lg uppercase leading-tight">{team.name}</span>
                  <span className="block truncate text-sm text-muted">
                    {team.race} · {team.coach_name}
                  </span>
                </span>
              </button>
            );
          })}
        </div>
      )}
      {teamId && (
        <section className="mt-6 rounded-3xl border border-line bg-card p-4">
          <h2 className="mb-3 text-center font-display text-xl uppercase">PIN del entrenador</h2>
          <PinPad
            value={pin}
            onChange={(next) => {
              setPin(next);
              if (next.length === 4) void enter(next);
            }}
          />
          <div className="mt-4">
            <BigButton disabled={pin.length !== 4 || busy} onClick={() => void enter()}>
              {busy ? "Entrando…" : "Entrar"}
            </BigButton>
          </div>
        </section>
      )}
    </main>
  );
}
