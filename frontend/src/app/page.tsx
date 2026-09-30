"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { PinPad } from "@/components/PinPad";
import { Alert, Spinner } from "@/components/ui";
import { api, session } from "@/lib/api";
import type { LoginOption } from "@/lib/types";

export default function LoginPage() {
  const router = useRouter();
  const [teams, setTeams] = useState<LoginOption[] | null>(null);
  const [teamId, setTeamId] = useState<number | null>(null);
  const [pin, setPin] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<LoginOption[]>("/api/auth/teams")
      .then((data) => {
        setTeams(data);
        const remembered = session.teamId;
        if (remembered && data.some((t) => t.id === remembered)) setTeamId(remembered);
        else if (data.length) setTeamId(data[0].id);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  const submit = useCallback(
    async (candidate: string) => {
      if (!teamId || candidate.length !== 4 || busy) return;
      setBusy(true);
      setError(null);
      try {
        const result = await api<{ token: string; team_id: number; team_name: string }>(
          "/api/auth/login",
          { method: "POST", body: { team_id: teamId, pin: candidate } },
        );
        session.save(result.token, result.team_id, result.team_name);
        router.push("/equipo");
      } catch (err) {
        setError((err as Error).message);
        setPin("");
      } finally {
        setBusy(false);
      }
    },
    [teamId, busy, router],
  );

  const selected = teams?.find((t) => t.id === teamId);

  return (
    <div className="mx-auto flex min-h-[100dvh] w-full max-w-md flex-col justify-center gap-6 px-5 py-8">
      <div className="text-center">
        <p className="text-5xl">{"\u{1F3C8}"}</p>
        <h1 className="mt-2 text-3xl font-black uppercase tracking-tight text-stone-50">
          Liga Blood Bowl
        </h1>
        <p className="text-sm text-stone-400">Edicion 2020 &middot; Asistente de mesa</p>
      </div>

      {teams === null ? (
        <Spinner label="Buscando equipos..." />
      ) : (
        <div className="card space-y-5">
          <div>
            <label className="label" htmlFor="team">
              Tu equipo
            </label>
            <select
              id="team"
              className="input appearance-none"
              value={teamId ?? ""}
              onChange={(event) => {
                setTeamId(Number(event.target.value));
                setPin("");
                setError(null);
              }}
            >
              {teams.map((team) => (
                <option key={team.id} value={team.id}>
                  {team.logo} {team.name} ({team.coach_name})
                </option>
              ))}
            </select>
            {selected && <p className="mt-1.5 text-xs text-stone-500">{selected.race}</p>}
          </div>

          <div>
            <span className="label">PIN de 4 digitos</span>
            <PinPad value={pin} onChange={setPin} onComplete={submit} disabled={busy} />
          </div>

          {error && <Alert onDismiss={() => setError(null)}>{error}</Alert>}

          <button
            type="button"
            className="btn-primary w-full"
            disabled={pin.length !== 4 || busy}
            onClick={() => submit(pin)}
          >
            {busy ? "Entrando..." : "Entrar al vestuario"}
          </button>
        </div>
      )}

      <div className="text-center">
        <Link href="/admin" className="text-xs text-stone-600 underline-offset-4 hover:underline">
          Acceso del comisario
        </Link>
      </div>
    </div>
  );
}
