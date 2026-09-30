import React from 'react';
import { Shield, ShieldAlert, LogOut, User, Trophy, Calendar } from 'lucide-react';

export default function Navbar({ activeTeam, onLogout, onOpenAdmin, leagueState, onSelectTab, currentTab }) {
  return (
    <header className="sticky top-0 z-40 bg-slate-900/95 backdrop-blur-md border-b border-slate-800 px-4 py-3 shadow-md">
      <div className="max-w-5xl mx-auto flex items-center justify-between">
        {/* Logo & Round */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-blood-600 to-blood-800 rounded-xl flex items-center justify-center shadow-lg shadow-blood-950/50 border border-blood-500/30">
            <Trophy className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="font-extrabold text-sm sm:text-base tracking-wide text-white flex items-center gap-1.5">
              BLOOD BOWL <span className="text-blood-500">BB2020</span>
            </h1>
            <div className="flex items-center gap-1.5 text-xs text-slate-400">
              <Calendar className="w-3 h-3 text-slate-400" />
              <span>Jornada {leagueState?.current_round || 1} de {leagueState?.total_rounds || 7}</span>
            </div>
          </div>
        </div>

        {/* Right side actions */}
        <div className="flex items-center gap-2">
          {activeTeam ? (
            <div className="flex items-center gap-2">
              <div className="hidden sm:flex flex-col text-right">
                <span className="text-xs font-bold text-white">{activeTeam.name}</span>
                <span className="text-[10px] text-blood-400">{activeTeam.coach_name} ({activeTeam.race})</span>
              </div>
              <button
                onClick={onLogout}
                title="Cambiar de Equipo"
                className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl border border-slate-700 transition"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <span className="text-xs text-slate-400">Sin equipo</span>
          )}

          <button
            onClick={onOpenAdmin}
            title="Panel de Comisionado"
            className="p-2 bg-blood-950/60 hover:bg-blood-900/80 text-blood-400 hover:text-blood-300 rounded-xl border border-blood-800/50 transition flex items-center gap-1 text-xs font-semibold"
          >
            <ShieldAlert className="w-4 h-4" />
            <span className="hidden md:inline">Admin</span>
          </button>
        </div>
      </div>
    </header>
  );
}
