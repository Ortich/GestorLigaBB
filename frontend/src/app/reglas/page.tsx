"use client";

import { useState } from "react";

import { AppShell } from "@/components/AppShell";
import { Alert, Spinner } from "@/components/ui";
import { formatGold } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { RuleEntry, Rules } from "@/lib/types";

type Section = "clima" | "patada" | "plegarias" | "heridas" | "incentivos" | "liga";

const SECTIONS: { id: Section; label: string }[] = [
  { id: "clima", label: "Clima" },
  { id: "patada", label: "Patada inicial" },
  { id: "plegarias", label: "Plegarias" },
  { id: "heridas", label: "Heridas" },
  { id: "incentivos", label: "Incentivos" },
  { id: "liga", label: "Reglas de liga" },
];

export default function RulesPage() {
  const [section, setSection] = useState<Section>("clima");
  const rules = useApi<Rules>("/api/rules");

  return (
    <AppShell title="Reglas" subtitle={rules.data?.edition}>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {SECTIONS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setSection(item.id)}
            className={`btn btn-sm whitespace-nowrap ${
              section === item.id ? "bg-gold-500 text-pitch-950" : "btn-secondary"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      {rules.error && <Alert>{rules.error}</Alert>}
      {rules.loading && !rules.data && <Spinner />}

      {rules.data && (
        <>
          {section === "clima" && (
            <RuleTable title={rules.data.weather.title} dice={rules.data.weather.dice} entries={rules.data.weather.entries} />
          )}
          {section === "patada" && (
            <RuleTable title={rules.data.kick_off.title} dice={rules.data.kick_off.dice} entries={rules.data.kick_off.entries} />
          )}
          {section === "plegarias" && (
            <RuleTable
              title={rules.data.prayers_to_nuffle.title}
              dice={rules.data.prayers_to_nuffle.dice}
              entries={rules.data.prayers_to_nuffle.entries}
            />
          )}
          {section === "heridas" && (
            <RuleTable
              title={rules.data.casualty_table.title}
              dice={rules.data.casualty_table.dice}
              entries={rules.data.casualty_table.entries}
            />
          )}

          {section === "incentivos" && (
            <>
              <p className="text-xs text-stone-500">{rules.data.inducements.note}</p>
              <div className="space-y-2">
                {rules.data.inducements.catalog.map((item) => (
                  <div key={item.code} className="card-tight">
                    <div className="flex items-baseline justify-between gap-3">
                      <p className="font-semibold text-stone-100">
                        {item.icon} {item.name}
                      </p>
                      <p className="shrink-0 text-sm font-bold text-gold-400">
                        {item.cost ? formatGold(item.cost) : "Variable"}
                      </p>
                    </div>
                    <p className="mt-1 text-sm text-stone-400">{item.text}</p>
                    <p className="mt-1 text-[11px] text-stone-600">Maximo {item.max} por partido</p>
                  </div>
                ))}
              </div>
            </>
          )}

          {section === "liga" && (
            <div className="space-y-3">
              <InfoCard title="Puntuacion y desempates" text={rules.data.scoring.text}>
                <ol className="mt-2 list-inside list-decimal text-sm text-stone-300">
                  {rules.data.scoring.tiebreakers.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ol>
              </InfoCard>
              <InfoCard title="Valoracion Actual de Equipo (VAE)" text={rules.data.ctv.text} />
              <InfoCard title={rules.data.rookie_safety.title} text={rules.data.rookie_safety.text} />
              <InfoCard title="Postpartido" text={rules.data.post_match.text} />
              <InfoCard title="Patrocinadores dinamicos" text={rules.data.sponsor_rules.text}>
                <ul className="mt-2 space-y-2">
                  {rules.data.sponsors.map((sponsor) => (
                    <li key={sponsor.code} className="rounded-lg bg-pitch-800/70 p-2.5">
                      <p className="text-sm font-semibold text-stone-100">{sponsor.name}</p>
                      <p className="text-xs text-stone-400">{sponsor.description}</p>
                      <p className="mt-1 text-xs text-gold-400">{sponsor.benefit}</p>
                    </li>
                  ))}
                </ul>
              </InfoCard>
              <InfoCard title="Puntos de estrella (SPP)" text={String(rules.data.spp.text ?? "")}>
                <ul className="mt-2 space-y-1 text-sm text-stone-300">
                  {rules.data.advancements.map((item) => (
                    <li key={item.code} className="flex justify-between gap-3">
                      <span>{item.name}</span>
                      <span className="shrink-0 text-stone-400">
                        {item.spp} SPP &middot; +{formatGold(item.value)}
                      </span>
                    </li>
                  ))}
                </ul>
              </InfoCard>
            </div>
          )}
        </>
      )}
    </AppShell>
  );
}

function RuleTable({ title, dice, entries }: { title: string; dice: string; entries: RuleEntry[] }) {
  return (
    <>
      <h2 className="section-title">
        {title} <span className="text-stone-500">({dice})</span>
      </h2>
      <div className="space-y-2">
        {entries.map((entry) => (
          <div key={`${entry.roll}-${entry.name}`} className="card-tight flex gap-3">
            <span className="flex h-10 w-12 shrink-0 items-center justify-center rounded-lg bg-pitch-800 text-sm font-bold text-gold-400">
              {entry.roll}
            </span>
            <div className="min-w-0">
              <p className="font-semibold text-stone-100">{entry.name}</p>
              <p className="text-sm text-stone-400">{entry.text}</p>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

function InfoCard({
  title,
  text,
  children,
}: {
  title: string;
  text: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="card">
      <h3 className="mb-1 font-bold text-gold-400">{title}</h3>
      <p className="text-sm text-stone-300">{text}</p>
      {children}
    </div>
  );
}
