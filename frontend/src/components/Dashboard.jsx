import React, { useState } from 'react';
import { 
  Trophy, Users, Calendar, Coins, ShieldCheck, HeartPulse, Sparkles, 
  ChevronRight, Swords, Skull, PlusCircle, AlertTriangle, HelpCircle, 
  Activity, Star
} from 'lucide-react';
import RuleModal from './RuleModal';

export default function Dashboard({ 
  teamDetail, 
  leagueInfo, 
  matches, 
  onOpenMatch, 
  onRefresh, 
  onHirePlayer 
}) {
  const [activeTab, setActiveTab] = useState('roster'); // 'roster', 'standings', 'matches'
  const [selectedRound, setSelectedRound] = useState(leagueInfo?.current_round || 1);
  const [selectedSkillPlayer, setSelectedSkillPlayer] = useState(null);
  const [selectedSponsorInfo, setSelectedSponsorInfo] = useState(null);
  const [showHireModal, setShowHireModal] = useState(false);

  // New Player Form State
  const [newPlayer, setNewPlayer] = useState({
    name: '',
    position: 'Lineman',
    number: (teamDetail?.players?.length || 0) + 1,
    ma: 6,
    st: 3,
    ag: '3+',
    pa: '4+',
    av: '9+',
    skills: '',
    cost: 50000,
  });

  const team = teamDetail?.team;
  const players = teamDetail?.players || [];
  const standings = leagueInfo?.standings || [];

  // Find next or active match for this team
  const myCurrentMatch = matches.find(
    m => (m.home_team_id === team?.id || m.away_team_id === team?.id) && m.round_number === leagueInfo?.current_round
  );

  const handleHireSubmit = async (e) => {
    e.preventDefault();
    await onHirePlayer(team.id, newPlayer);
    setShowHireModal(false);
    setNewPlayer({
      name: '',
      position: 'Lineman',
      number: players.length + 2,
      ma: 6,
      st: 3,
      ag: '3+',
      pa: '4+',
      av: '9+',
      skills: '',
      cost: 50000,
    });
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'ACTIVE':
        return <span className="px-2 py-0.5 bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-full text-[10px] font-bold">ACTIVO</span>;
      case 'MNG':
        return <span className="px-2 py-0.5 bg-amber-500/20 text-amber-400 border border-amber-500/30 rounded-full text-[10px] font-bold">PIERDE PARTIDO (MNG)</span>;
      case 'DEAD':
        return <span className="px-2 py-0.5 bg-red-600/30 text-red-400 border border-red-500/40 rounded-full text-[10px] font-bold flex items-center gap-1"><Skull className="w-2.5 h-2.5" /> MUERTO</span>;
      default:
        return null;
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-4 space-y-5 pb-20">
      {/* 1. TEAM HEADER CARD */}
      {team && (
        <div className="bg-gradient-to-br from-slate-900 to-slate-950 border border-slate-800 rounded-3xl p-5 shadow-xl relative overflow-hidden">
          <div className="absolute top-0 right-0 w-48 h-48 bg-blood-600/10 rounded-full blur-3xl pointer-events-none" />
          
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold uppercase tracking-wider text-blood-400">{team.race}</span>
                {team.current_sponsor && (
                  <button
                    onClick={() => setSelectedSponsorInfo(team.current_sponsor)}
                    className="flex items-center gap-1 px-2.5 py-0.5 bg-amber-500/20 border border-amber-500/40 text-amber-300 rounded-full text-[11px] font-bold hover:bg-amber-500/30 transition"
                  >
                    <Sparkles className="w-3 h-3 text-amber-400" />
                    <span>{team.current_sponsor.name}</span>
                  </button>
                )}
              </div>
              <h2 className="text-2xl font-black text-white tracking-tight">{team.name}</h2>
              <p className="text-xs text-slate-400">Entrenador: <span className="text-slate-200 font-semibold">{team.coach_name}</span></p>
            </div>

            {/* Highlighted CTV & Treasury */}
            <div className="flex items-center gap-3">
              <div className="bg-slate-950/80 border border-slate-800 rounded-2xl px-4 py-2.5 text-center shadow-inner">
                <div className="text-[10px] uppercase font-bold text-slate-400">VAE / CTV</div>
                <div className="text-lg font-black text-blood-400">
                  {(team.ctv / 1000).toLocaleString()}k
                </div>
              </div>

              <div className="bg-slate-950/80 border border-slate-800 rounded-2xl px-4 py-2.5 text-center shadow-inner">
                <div className="text-[10px] uppercase font-bold text-slate-400 flex items-center justify-center gap-1">
                  <Coins className="w-3 h-3 text-amber-400" />
                  <span>Tesorería</span>
                </div>
                <div className="text-lg font-black text-amber-400">
                  {(team.treasury / 1000).toLocaleString()}k
                </div>
              </div>
            </div>
          </div>

          {/* Quick Roster Stats Grid */}
          <div className="grid grid-cols-4 gap-2 pt-3 border-t border-slate-800/80 text-center text-xs">
            <div className="bg-slate-900/60 p-2 rounded-xl">
              <div className="text-slate-400 text-[10px]">Rerolls</div>
              <div className="font-bold text-white">{team.rerolls}</div>
            </div>
            <div className="bg-slate-900/60 p-2 rounded-xl">
              <div className="text-slate-400 text-[10px]">Apotecario</div>
              <div className="font-bold text-emerald-400">{team.apothecary ? 'Sí' : 'No'}</div>
            </div>
            <div className="bg-slate-900/60 p-2 rounded-xl">
              <div className="text-slate-400 text-[10px]">Asistentes</div>
              <div className="font-bold text-white">{team.assistant_coaches}</div>
            </div>
            <div className="bg-slate-900/60 p-2 rounded-xl">
              <div className="text-slate-400 text-[10px]">Animadoras</div>
              <div className="font-bold text-white">{team.cheerleaders}</div>
            </div>
          </div>
        </div>
      )}

      {/* 2. MATCH CALLOUT CARD (NEXT MATCH ASSISTANT LAUNCHER) */}
      {myCurrentMatch && (
        <div className="bg-gradient-to-r from-blood-950/70 via-slate-900 to-slate-900 border-2 border-blood-600/40 rounded-3xl p-5 shadow-2xl relative">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 bg-blood-500 rounded-full animate-pulse" />
              <span className="text-xs font-black uppercase tracking-wider text-blood-400">
                Jornada {myCurrentMatch.round_number}
              </span>
            </div>
            <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase ${
              myCurrentMatch.status === 'IN_PROGRESS' 
                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                : myCurrentMatch.status === 'COMPLETED'
                ? 'bg-slate-800 text-slate-400'
                : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
            }`}>
              {myCurrentMatch.status === 'SCHEDULED' ? 'Pendiente' : 
               myCurrentMatch.status === 'READY_CHECK' ? 'Ready Check' :
               myCurrentMatch.status === 'PRE_MATCH' ? 'Prepartido' :
               myCurrentMatch.status === 'IN_PROGRESS' ? 'En Vivo' : 'Completado'}
            </span>
          </div>

          <div className="flex items-center justify-between gap-4 py-2">
            <div className="flex-1 text-center sm:text-left">
              <div className="text-sm font-extrabold text-white truncate">{myCurrentMatch.home_team_name}</div>
              <div className="text-[11px] text-slate-400">{myCurrentMatch.home_race} (Local)</div>
            </div>

            <div className="flex items-center gap-3 px-3 py-1.5 bg-slate-950/80 rounded-2xl border border-slate-800">
              <span className="text-2xl font-black text-white">{myCurrentMatch.home_td}</span>
              <span className="text-xs font-bold text-slate-500">vs</span>
              <span className="text-2xl font-black text-white">{myCurrentMatch.away_td}</span>
            </div>

            <div className="flex-1 text-center sm:text-right">
              <div className="text-sm font-extrabold text-white truncate">{myCurrentMatch.away_team_name}</div>
              <div className="text-[11px] text-slate-400">{myCurrentMatch.away_race} (Visitante)</div>
            </div>
          </div>

          {/* Active Bounty banner */}
          {leagueInfo?.active_bounty_id && (
            <div className="mt-3 py-1.5 px-3 bg-slate-950/60 rounded-xl border border-slate-800/80 flex items-center justify-between text-xs">
              <span className="text-slate-400 flex items-center gap-1.5">
                <Star className="w-3.5 h-3.5 text-amber-400" />
                <span>Bounty Semanal:</span>
              </span>
              <span className="font-bold text-amber-300">Cazador de Cabezas (+10k mo por cada baja)</span>
            </div>
          )}

          <button
            onClick={() => onOpenMatch(myCurrentMatch.id)}
            className="w-full mt-4 py-3.5 bg-gradient-to-r from-blood-600 to-blood-700 hover:from-blood-500 hover:to-blood-600 active:scale-[0.99] text-white font-black text-sm uppercase tracking-wider rounded-2xl shadow-xl shadow-blood-950 flex items-center justify-center gap-2 transition-all"
          >
            <Swords className="w-4 h-4" />
            <span>Abrir Asistente de Partido</span>
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* 3. MOBILE NAVIGATION TABS */}
      <div className="flex p-1 bg-slate-900 border border-slate-800 rounded-2xl shadow-md">
        <button
          onClick={() => setActiveTab('roster')}
          className={`flex-1 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-2 ${
            activeTab === 'roster'
              ? 'bg-blood-600 text-white shadow-md'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          <Users className="w-4 h-4" />
          <span>Plantilla ({players.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('standings')}
          className={`flex-1 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-2 ${
            activeTab === 'standings'
              ? 'bg-blood-600 text-white shadow-md'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          <Trophy className="w-4 h-4" />
          <span>Clasificación</span>
        </button>

        <button
          onClick={() => setActiveTab('matches')}
          className={`flex-1 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-2 ${
            activeTab === 'matches'
              ? 'bg-blood-600 text-white shadow-md'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          <Calendar className="w-4 h-4" />
          <span>Jornadas</span>
        </button>
      </div>

      {/* 4. TAB CONTENTS */}

      {/* TAB 1: ROSTER */}
      {activeTab === 'roster' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-extrabold text-white flex items-center gap-2">
              <span>Jugadores del Equipo</span>
              <span className="text-xs font-normal text-slate-400">
                ({players.filter(p => p.status === 'ACTIVE').length} activos)
              </span>
            </h3>

            <button
              onClick={() => setShowHireModal(true)}
              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-xl text-xs font-bold flex items-center gap-1.5 transition"
            >
              <PlusCircle className="w-4 h-4 text-emerald-400" />
              <span>Fichar Jugador</span>
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {players.map((player) => (
              <div
                key={player.id}
                className={`p-4 rounded-2xl border transition-all ${
                  player.status === 'DEAD'
                    ? 'bg-red-950/20 border-red-900/40 opacity-75'
                    : player.status === 'MNG'
                    ? 'bg-amber-950/20 border-amber-800/40'
                    : 'bg-slate-900/90 border-slate-800 hover:border-slate-700'
                } shadow-md`}
              >
                {/* Header */}
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2.5">
                    <span className="w-7 h-7 bg-slate-950 border border-slate-800 rounded-xl flex items-center justify-center font-black text-xs text-blood-400 shrink-0">
                      #{player.number}
                    </span>
                    <div>
                      <h4 className="font-extrabold text-sm text-white leading-tight">{player.name}</h4>
                      <p className="text-[11px] text-slate-400 font-semibold">{player.position}</p>
                    </div>
                  </div>
                  <div>{getStatusBadge(player.status)}</div>
                </div>

                {/* Stats Table (Mobile Optimized Badges) */}
                <div className="grid grid-cols-5 gap-1.5 my-2.5 text-center">
                  <div className="bg-slate-950 p-1 rounded-lg border border-slate-800/80">
                    <div className="text-[9px] uppercase font-bold text-slate-400">MA</div>
                    <div className="text-xs font-black text-white">{player.ma}</div>
                  </div>
                  <div className="bg-slate-950 p-1 rounded-lg border border-slate-800/80">
                    <div className="text-[9px] uppercase font-bold text-slate-400">ST</div>
                    <div className="text-xs font-black text-white">{player.st}</div>
                  </div>
                  <div className="bg-slate-950 p-1 rounded-lg border border-slate-800/80">
                    <div className="text-[9px] uppercase font-bold text-slate-400">AG</div>
                    <div className="text-xs font-black text-white">{player.ag}</div>
                  </div>
                  <div className="bg-slate-950 p-1 rounded-lg border border-slate-800/80">
                    <div className="text-[9px] uppercase font-bold text-slate-400">PA</div>
                    <div className="text-xs font-black text-white">{player.pa}</div>
                  </div>
                  <div className="bg-slate-950 p-1 rounded-lg border border-slate-800/80">
                    <div className="text-[9px] uppercase font-bold text-slate-400">AV</div>
                    <div className="text-xs font-black text-white">{player.av}</div>
                  </div>
                </div>

                {/* Skills & SPP */}
                <div className="flex items-center justify-between pt-2 border-t border-slate-800/60 text-xs">
                  <div className="flex-1 mr-2 truncate">
                    {player.skills ? (
                      <button
                        onClick={() => setSelectedSkillPlayer(player)}
                        className="text-[11px] text-blood-400 font-semibold hover:underline flex items-center gap-1 truncate"
                      >
                        <span className="truncate">{player.skills}</span>
                        <HelpCircle className="w-3 h-3 shrink-0" />
                      </button>
                    ) : (
                      <span className="text-[11px] text-slate-500 italic">Sin habilidades</span>
                    )}
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <span className="px-2 py-0.5 bg-slate-950 border border-slate-800 rounded-lg text-[10px] font-bold text-amber-400">
                      {player.spp} SPP
                    </span>
                    <span className="text-[10px] text-slate-400">
                      {(player.current_value / 1000)}k
                    </span>
                  </div>
                </div>

                {player.injuries && (
                  <div className="mt-2 text-[10px] text-red-400 bg-red-950/40 border border-red-900/40 p-1.5 rounded-lg flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3 shrink-0" />
                    <span>Lesión: {player.injuries}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 2: STANDINGS */}
      {activeTab === 'standings' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-extrabold text-white flex items-center gap-2">
              <Trophy className="w-4 h-4 text-amber-400" />
              <span>Tabla de Clasificación</span>
            </h3>
            <span className="text-xs text-slate-400">Desempate: 1º Dif TD, 2º Dif Bajas</span>
          </div>

          <div className="space-y-2">
            {standings.map((row) => {
              const isMyTeam = row.team_id === team?.id;
              const isLast = row.rank === standings.length;
              const isLeader = row.rank === 1;

              return (
                <div
                  key={row.team_id}
                  className={`p-3.5 rounded-2xl border transition-all ${
                    isMyTeam
                      ? 'bg-blood-950/30 border-blood-500/60 shadow-lg shadow-blood-950/40'
                      : 'bg-slate-900/80 border-slate-800'
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <span className={`w-8 h-8 rounded-xl flex items-center justify-center font-black text-sm shrink-0 ${
                        isLeader
                          ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20'
                          : isLast
                          ? 'bg-red-950 text-red-400 border border-red-800'
                          : 'bg-slate-950 text-slate-300 border border-slate-800'
                      }`}>
                        {row.rank}
                      </span>
                      <div>
                        <div className="font-extrabold text-sm text-white flex items-center gap-2">
                          <span>{row.team_name}</span>
                          {isMyTeam && (
                            <span className="px-1.5 py-0.2 bg-blood-600 text-[9px] font-black uppercase text-white rounded">
                              Tú
                            </span>
                          )}
                          {row.current_sponsor_id && (
                            <span className="text-[10px] text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/20">
                              Sponsor
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-slate-400 font-medium">
                          {row.coach_name} ({row.race})
                        </div>
                      </div>
                    </div>

                    <div className="text-right">
                      <div className="text-xl font-black text-white">{row.pts} <span className="text-xs text-slate-400 font-bold">PTS</span></div>
                    </div>
                  </div>

                  {/* Secondary Metrics Bar */}
                  <div className="grid grid-cols-4 gap-2 mt-2 pt-2 border-t border-slate-800/80 text-center text-[10px]">
                    <div>
                      <span className="text-slate-500">PJ / V-E-D: </span>
                      <span className="font-bold text-slate-300">{row.played} ({row.won}-{row.drawn}-{row.lost})</span>
                    </div>
                    <div>
                      <span className="text-slate-500">TDs: </span>
                      <span className="font-bold text-white">{row.td_for}:{row.td_against}</span>
                      <span className={`ml-1 font-bold ${row.td_diff >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                        ({row.td_diff > 0 ? `+${row.td_diff}` : row.td_diff})
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500">Bajas: </span>
                      <span className="font-bold text-white">{row.cas_for}</span>
                      <span className={`ml-1 font-bold ${row.cas_diff >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                        ({row.cas_diff > 0 ? `+${row.cas_diff}` : row.cas_diff})
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500">Faltas: </span>
                      <span className="font-bold text-slate-300">{row.fouls_committed}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* TAB 3: MATCHES CALENDAR */}
      {activeTab === 'matches' && (
        <div className="space-y-4">
          {/* Round Selector Pill Bar */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-2 scrollbar-none">
            {[1, 2, 3, 4, 5, 6, 7].map((r) => (
              <button
                key={r}
                onClick={() => setSelectedRound(r)}
                className={`px-4 py-2 rounded-xl text-xs font-extrabold whitespace-nowrap transition-all ${
                  selectedRound === r
                    ? 'bg-blood-600 text-white shadow-md'
                    : 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-white'
                }`}
              >
                Jornada {r}
              </button>
            ))}
          </div>

          <div className="space-y-3">
            {matches
              .filter((m) => m.round_number === selectedRound)
              .map((match) => (
                <div
                  key={match.id}
                  className="p-4 bg-slate-900/90 border border-slate-800 rounded-2xl shadow-md"
                >
                  <div className="flex items-center justify-between mb-3 text-xs">
                    <span className="font-bold text-slate-400">Partido #{match.id}</span>
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                      match.status === 'COMPLETED'
                        ? 'bg-slate-800 text-slate-400'
                        : match.status === 'IN_PROGRESS'
                        ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                        : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                    }`}>
                      {match.status}
                    </span>
                  </div>

                  <div className="flex items-center justify-between gap-3">
                    <div className="flex-1">
                      <div className="font-extrabold text-sm text-white">{match.home_team_name}</div>
                      <div className="text-[11px] text-slate-400">{match.home_race}</div>
                    </div>

                    <div className="px-3 py-1 bg-slate-950 border border-slate-800 rounded-xl font-black text-lg text-white">
                      {match.home_td} - {match.away_td}
                    </div>

                    <div className="flex-1 text-right">
                      <div className="font-extrabold text-sm text-white">{match.away_team_name}</div>
                      <div className="text-[11px] text-slate-400">{match.away_race}</div>
                    </div>
                  </div>

                  <button
                    onClick={() => onOpenMatch(match.id)}
                    className="w-full mt-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-xl text-xs font-bold transition flex items-center justify-center gap-1.5"
                  >
                    <span>Ver Asistente de Partido</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* SKILLS MODAL */}
      {selectedSkillPlayer && (
        <RuleModal
          isOpen={true}
          onClose={() => setSelectedSkillPlayer(null)}
          title={`Habilidades: ${selectedSkillPlayer.name}`}
          subtitle={`${selectedSkillPlayer.position} (#${selectedSkillPlayer.number})`}
          content={
            <div className="space-y-3">
              <div>
                <span className="font-bold text-white">Habilidades activas:</span>
                <p className="mt-1 text-blood-400 font-bold">{selectedSkillPlayer.skills}</p>
              </div>
              <div className="text-xs text-slate-400 border-t border-slate-800 pt-2">
                Consulta los efectos oficiales de Placaje (Block), Esquivar (Dodge), Pasar (Pass), Manos Seguras (Sure Hands) o Regeneración en el reglamento de Blood Bowl BB2020.
              </div>
            </div>
          }
        />
      )}

      {/* SPONSOR MODAL */}
      {selectedSponsorInfo && (
        <RuleModal
          isOpen={true}
          onClose={() => setSelectedSponsorInfo(null)}
          title={`Sponsor: ${selectedSponsorInfo.name}`}
          subtitle="Mecánica de Recuperación (Catch-up)"
          content={
            <div className="space-y-3">
              <p className="text-slate-300">{selectedSponsorInfo.description}</p>
              <div className="p-3 bg-amber-950/40 border border-amber-800/40 rounded-xl text-amber-300 font-bold text-xs">
                Beneficio activo: {selectedSponsorInfo.benefit}
              </div>
            </div>
          }
        />
      )}

      {/* HIRE PLAYER MODAL */}
      {showHireModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-md w-full p-6 shadow-2xl relative">
            <h3 className="text-lg font-black text-white mb-4 flex items-center gap-2">
              <PlusCircle className="w-5 h-5 text-emerald-400" />
              <span>Fichar Nuevo Jugador</span>
            </h3>

            <form onSubmit={handleHireSubmit} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-400 font-bold mb-1">Nombre</label>
                <input
                  type="text"
                  required
                  value={newPlayer.name}
                  onChange={(e) => setNewPlayer({ ...newPlayer, name: e.target.value })}
                  placeholder="Ej. Borak el Fuerte"
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl p-2.5 text-white focus:border-blood-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-slate-400 font-bold mb-1">Posición</label>
                  <input
                    type="text"
                    required
                    value={newPlayer.position}
                    onChange={(e) => setNewPlayer({ ...newPlayer, position: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl p-2.5 text-white"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 font-bold mb-1">Dorsal (#)</label>
                  <input
                    type="number"
                    required
                    value={newPlayer.number}
                    onChange={(e) => setNewPlayer({ ...newPlayer, number: parseInt(e.target.value) || 1 })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl p-2.5 text-white"
                  />
                </div>
              </div>

              <div className="grid grid-cols-5 gap-1.5 text-center">
                <div>
                  <label className="text-[10px] text-slate-400 font-bold">MA</label>
                  <input
                    type="number"
                    value={newPlayer.ma}
                    onChange={(e) => setNewPlayer({ ...newPlayer, ma: parseInt(e.target.value) || 6 })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg p-1.5 text-center text-white"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-400 font-bold">ST</label>
                  <input
                    type="number"
                    value={newPlayer.st}
                    onChange={(e) => setNewPlayer({ ...newPlayer, st: parseInt(e.target.value) || 3 })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg p-1.5 text-center text-white"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-400 font-bold">AG</label>
                  <input
                    type="text"
                    value={newPlayer.ag}
                    onChange={(e) => setNewPlayer({ ...newPlayer, ag: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg p-1.5 text-center text-white"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-400 font-bold">PA</label>
                  <input
                    type="text"
                    value={newPlayer.pa}
                    onChange={(e) => setNewPlayer({ ...newPlayer, pa: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg p-1.5 text-center text-white"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-400 font-bold">AV</label>
                  <input
                    type="text"
                    value={newPlayer.av}
                    onChange={(e) => setNewPlayer({ ...newPlayer, av: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg p-1.5 text-center text-white"
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-400 font-bold mb-1">Habilidades iniciales (separadas por coma)</label>
                <input
                  type="text"
                  placeholder="Block, Dodge"
                  value={newPlayer.skills}
                  onChange={(e) => setNewPlayer({ ...newPlayer, skills: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl p-2.5 text-white"
                />
              </div>

              <div>
                <label className="block text-slate-400 font-bold mb-1">Coste (mo)</label>
                <input
                  type="number"
                  step="10000"
                  required
                  value={newPlayer.cost}
                  onChange={(e) => setNewPlayer({ ...newPlayer, cost: parseInt(e.target.value) || 50000 })}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl p-2.5 text-white"
                />
                <span className="text-[11px] text-slate-500">
                  Tesorería disponible: {(team.treasury).toLocaleString()} mo
                </span>
              </div>

              <div className="flex gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowHireModal(false)}
                  className="flex-1 py-3 bg-slate-800 text-slate-300 font-bold rounded-xl"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="flex-1 py-3 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-xl shadow-lg"
                >
                  Confirmar Fichaje
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
