import React, { useState, useEffect } from 'react';
import { 
  ArrowLeft, CheckCircle2, AlertCircle, Dices, Swords, Trophy, 
  HelpCircle, Shield, ShoppingCart, Plus, Minus, Trash2, Undo2, 
  ChevronRight, Sparkles, Skull, HeartPulse, Clock, Flag, Award
} from 'lucide-react';
import { api } from '../api';
import RuleModal from './RuleModal';

export default function MatchAssistant({ matchId, onBack, onMatchUpdated, rulesData }) {
  const [matchData, setMatchData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTeamTab, setActiveTeamTab] = useState('home'); // 'home' | 'away'
  const [activeRuleModal, setActiveRuleModal] = useState(null); // { title, subtitle, content }

  // Ready Check PIN states
  const [homePin, setHomePin] = useState('');
  const [awayPin, setAwayPin] = useState('');

  // Incentives Cart
  const [selectedIncentives, setSelectedIncentives] = useState({});

  // Manual Roll Inputs
  const [manualWeather, setManualWeather] = useState('');
  const [manualPrayers, setManualPrayers] = useState('');
  const [manualKick, setManualKick] = useState('');

  // Completion State
  const [showCompletionModal, setShowCompletionModal] = useState(false);
  const [homeWinningsRoll, setHomeWinningsRoll] = useState(null);
  const [awayWinningsRoll, setAwayWinningsRoll] = useState(null);
  const [selectedMvpHomes, setSelectedMvpHomes] = useState('');
  const [selectedMvpAway, setSelectedMvpAway] = useState('');
  const [casualtiesReport, setCasualtiesReport] = useState([]); // [{ player_id, outcome, injury }]

  const loadMatch = async () => {
    try {
      setLoading(true);
      const data = await api.getMatchDetail(matchId);
      setMatchData(data);
      setError('');
    } catch (err) {
      setError(err.message || 'Error al cargar partido.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMatch();
  }, [matchId]);

  if (loading && !matchData) {
    return (
      <div className="max-w-md mx-auto p-6 text-center text-slate-400">
        <div className="animate-spin w-8 h-8 border-4 border-blood-500 border-t-transparent rounded-full mx-auto mb-3" />
        <p>Cargando Asistente de Partido...</p>
      </div>
    );
  }

  if (error && !matchData) {
    return (
      <div className="max-w-md mx-auto p-6 text-center">
        <div className="p-4 bg-red-950/60 border border-red-800 rounded-2xl text-red-300 text-sm mb-4">
          {error}
        </div>
        <button
          onClick={onBack}
          className="px-4 py-2 bg-slate-800 text-white rounded-xl text-xs font-bold"
        >
          Volver
        </button>
      </div>
    );
  }

  const { match, home_team, away_team, home_players, away_players, events, petty_cash_info } = matchData;

  // Handlers for Ready Check
  const handleReadyCheck = async (teamId, pin) => {
    try {
      setError('');
      await api.readyCheck(matchId, teamId, pin);
      await loadMatch();
      onMatchUpdated && onMatchUpdated();
    } catch (err) {
      setError(err.message || 'PIN inválido.');
    }
  };

  // Handlers for Rolls
  const handleRoll = async (rollType, manualVal = null) => {
    try {
      setError('');
      const val = manualVal ? parseInt(manualVal) : null;
      const res = await api.rollDice(matchId, rollType, val);
      await loadMatch();
      setActiveRuleModal({
        title: res.name,
        subtitle: `Tirada de ${rollType.toUpperCase()}: ${res.roll_value}`,
        content: res.description
      });
      onMatchUpdated && onMatchUpdated();
    } catch (err) {
      setError(err.message || 'Error en la tirada.');
    }
  };

  // Handlers for Incentives
  const handleUpdateIncentiveQty = (incentive, delta) => {
    const current = selectedIncentives[incentive.id] || { ...incentive, qty: 0 };
    const newQty = Math.max(0, Math.min(incentive.max_qty, current.qty + delta));
    setSelectedIncentives({
      ...selectedIncentives,
      [incentive.id]: { ...incentive, qty: newQty }
    });
  };

  const handleSaveIncentives = async (teamId) => {
    try {
      setError('');
      const items = Object.values(selectedIncentives).filter(i => i.qty > 0);
      await api.buyIncentives(matchId, teamId, items);
      await loadMatch();
      onMatchUpdated && onMatchUpdated();
    } catch (err) {
      setError(err.message || 'Error al guardar incentivos.');
    }
  };

  // Handler for Start Match
  const handleStartMatch = async () => {
    try {
      setError('');
      await api.startMatch(matchId);
      await loadMatch();
      onMatchUpdated && onMatchUpdated();
    } catch (err) {
      setError(err.message || 'Error al iniciar partido.');
    }
  };

  // Handler for Events (TD, CAS, PASS, FOUL, INT)
  const handleAddEvent = async (teamId, playerId, eventType) => {
    try {
      setError('');
      await api.addMatchEvent(matchId, {
        team_id: teamId,
        player_id: playerId,
        event_type: eventType,
        turn: match.current_turn,
        half: match.current_half
      });
      await loadMatch();
      onMatchUpdated && onMatchUpdated();
    } catch (err) {
      setError(err.message || 'Error al registrar evento.');
    }
  };

  const handleDeleteEvent = async (eventId) => {
    try {
      setError('');
      await api.deleteMatchEvent(matchId, eventId);
      await loadMatch();
      onMatchUpdated && onMatchUpdated();
    } catch (err) {
      setError(err.message || 'Error al revertir evento.');
    }
  };

  const handleAdvanceTurn = async () => {
    let nextTurn = match.current_turn + 1;
    let nextHalf = match.current_half;
    if (nextTurn > 8 && nextHalf === 1) {
      nextTurn = 1;
      nextHalf = 2;
    } else if (nextTurn > 8 && nextHalf === 2) {
      nextTurn = 8;
    }
    await api.updateTurn(matchId, nextTurn, nextHalf);
    await loadMatch();
  };

  // Handler for Match Completion
  const handleFinalizeMatch = async () => {
    try {
      setError('');
      await api.completeMatch(matchId, {
        home_winnings_roll: homeWinningsRoll,
        away_winnings_roll: awayWinningsRoll,
        mvp_player_id_home: selectedMvpHomes ? parseInt(selectedMvpHomes) : null,
        mvp_player_id_away: selectedMvpAway ? parseInt(selectedMvpAway) : null,
        casualties: casualtiesReport
      });
      setShowCompletionModal(false);
      await loadMatch();
      onMatchUpdated && onMatchUpdated();
    } catch (err) {
      setError(err.message || 'Error al finalizar acta del partido.');
    }
  };

  const activePlayers = activeTeamTab === 'home' ? home_players : away_players;
  const currentTeamObj = activeTeamTab === 'home' ? home_team : away_team;

  // Calculate incentives cost
  const totalIncentivesCost = Object.values(selectedIncentives).reduce(
    (sum, item) => sum + (item.cost * (item.qty || 0)), 0
  );

  return (
    <div className="max-w-4xl mx-auto px-4 py-4 space-y-4 pb-24">
      {/* Top Header & Back Button */}
      <div className="flex items-center justify-between">
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 px-3 py-2 bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 rounded-xl text-xs font-bold transition"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Volver</span>
        </button>

        <div className="flex items-center gap-2">
          <span className="text-xs font-extrabold uppercase text-blood-400">
            Jornada {match.round_number}
          </span>
          <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase ${
            match.status === 'IN_PROGRESS' 
              ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
              : match.status === 'COMPLETED'
              ? 'bg-slate-800 text-slate-300'
              : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
          }`}>
            {match.status}
          </span>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-red-950/70 border border-red-800 rounded-2xl flex items-center gap-2 text-red-300 text-xs font-semibold">
          <AlertCircle className="w-4 h-4 shrink-0 text-red-400" />
          <span>{error}</span>
        </div>
      )}

      {/* MATCH STATE STEPPER */}
      <div className="grid grid-cols-4 gap-1.5 text-center text-[10px] font-black uppercase tracking-wider">
        <div className={`p-2 rounded-xl border ${
          match.status === 'READY_CHECK' || match.status === 'SCHEDULED'
            ? 'bg-blood-600 text-white border-blood-500'
            : 'bg-slate-900/60 text-slate-500 border-slate-800'
        }`}>
          1. Ready Check
        </div>
        <div className={`p-2 rounded-xl border ${
          match.status === 'PRE_MATCH'
            ? 'bg-blood-600 text-white border-blood-500'
            : 'bg-slate-900/60 text-slate-500 border-slate-800'
        }`}>
          2. Prepartido
        </div>
        <div className={`p-2 rounded-xl border ${
          match.status === 'IN_PROGRESS'
            ? 'bg-blood-600 text-white border-blood-500'
            : 'bg-slate-900/60 text-slate-500 border-slate-800'
        }`}>
          3. En Vivo
        </div>
        <div className={`p-2 rounded-xl border ${
          match.status === 'COMPLETED'
            ? 'bg-emerald-600 text-white border-emerald-500'
            : 'bg-slate-900/60 text-slate-500 border-slate-800'
        }`}>
          4. Cierre
        </div>
      </div>

      {/* ------------------------------------------------------------- */}
      {/* FASE 1: READY CHECK (PRESENCIAL CON PIN DE AMBOS ENTRENADORES) */}
      {/* ------------------------------------------------------------- */}
      {(match.status === 'SCHEDULED' || match.status === 'READY_CHECK') && (
        <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 shadow-xl space-y-6">
          <div className="text-center">
            <h3 className="text-xl font-black text-white">READY CHECK PRESENCIAL</h3>
            <p className="text-xs text-slate-400 mt-1">
              Ambos entrenadores deben introducir su PIN de 4 dígitos en este dispositivo para confirmar asistencia.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Home Coach Check */}
            <div className={`p-5 rounded-2xl border transition-all ${
              match.home_coach_ready
                ? 'bg-emerald-950/20 border-emerald-500/40'
                : 'bg-slate-950 border-slate-800'
            }`}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-bold text-slate-400 uppercase">Equipo Local</span>
                {match.home_coach_ready && (
                  <span className="flex items-center gap-1 text-xs text-emerald-400 font-bold">
                    <CheckCircle2 className="w-4 h-4" /> Listo
                  </span>
                )}
              </div>
              <h4 className="text-base font-extrabold text-white">{home_team.name}</h4>
              <p className="text-xs text-slate-400 mb-4">{home_team.coach_name} ({home_team.race})</p>

              {!match.home_coach_ready ? (
                <div className="space-y-3">
                  <input
                    type="password"
                    inputMode="numeric"
                    maxLength={4}
                    placeholder="PIN 4 dígitos"
                    value={homePin}
                    onChange={(e) => setHomePin(e.target.value.slice(0, 4))}
                    className="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 text-center text-lg font-black text-white tracking-widest focus:border-blood-500"
                  />
                  <button
                    onClick={() => handleReadyCheck(home_team.id, homePin)}
                    className="w-full py-3 bg-blood-600 hover:bg-blood-500 active:scale-[0.98] text-white font-extrabold text-xs uppercase tracking-wider rounded-xl shadow-lg transition"
                  >
                    Confirmar Local
                  </button>
                </div>
              ) : (
                <div className="py-2 text-center text-xs text-emerald-400 font-bold bg-emerald-950/40 rounded-xl border border-emerald-900/50">
                  Presencia confirmada
                </div>
              )}
            </div>

            {/* Away Coach Check */}
            <div className={`p-5 rounded-2xl border transition-all ${
              match.away_coach_ready
                ? 'bg-emerald-950/20 border-emerald-500/40'
                : 'bg-slate-950 border-slate-800'
            }`}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-bold text-slate-400 uppercase">Equipo Visitante</span>
                {match.away_coach_ready && (
                  <span className="flex items-center gap-1 text-xs text-emerald-400 font-bold">
                    <CheckCircle2 className="w-4 h-4" /> Listo
                  </span>
                )}
              </div>
              <h4 className="text-base font-extrabold text-white">{away_team.name}</h4>
              <p className="text-xs text-slate-400 mb-4">{away_team.coach_name} ({away_team.race})</p>

              {!match.away_coach_ready ? (
                <div className="space-y-3">
                  <input
                    type="password"
                    inputMode="numeric"
                    maxLength={4}
                    placeholder="PIN 4 dígitos"
                    value={awayPin}
                    onChange={(e) => setAwayPin(e.target.value.slice(0, 4))}
                    className="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 text-center text-lg font-black text-white tracking-widest focus:border-blood-500"
                  />
                  <button
                    onClick={() => handleReadyCheck(away_team.id, awayPin)}
                    className="w-full py-3 bg-blood-600 hover:bg-blood-500 active:scale-[0.98] text-white font-extrabold text-xs uppercase tracking-wider rounded-xl shadow-lg transition"
                  >
                    Confirmar Visitante
                  </button>
                </div>
              ) : (
                <div className="py-2 text-center text-xs text-emerald-400 font-bold bg-emerald-950/40 rounded-xl border border-emerald-900/50">
                  Presencia confirmada
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* FASE 2: PRE_MATCH (VAE, PETTY CASH, INCENTIVOS, CLIMA, PATADA) */}
      {/* ------------------------------------------------------------- */}
      {match.status === 'PRE_MATCH' && (
        <div className="space-y-5">
          {/* CTV & Petty Cash Comparison Card */}
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-5 shadow-xl space-y-4">
            <h3 className="text-base font-black text-white flex items-center justify-between">
              <span>Valoración Actual de Equipo (VAE)</span>
              <span className="text-xs text-slate-400 font-normal">Cálculo oficial BB2020</span>
            </h3>

            <div className="grid grid-cols-2 gap-3 text-center">
              <div className="bg-slate-950 p-4 rounded-2xl border border-slate-800">
                <div className="text-[11px] text-slate-400 font-bold">{home_team.name}</div>
                <div className="text-2xl font-black text-white mt-1">
                  {(match.home_ctv / 1000).toLocaleString()}k
                </div>
                <div className="text-[10px] text-slate-500">VAE Local</div>
              </div>

              <div className="bg-slate-950 p-4 rounded-2xl border border-slate-800">
                <div className="text-[11px] text-slate-400 font-bold">{away_team.name}</div>
                <div className="text-2xl font-black text-white mt-1">
                  {(match.away_ctv / 1000).toLocaleString()}k
                </div>
                <div className="text-[10px] text-slate-500">VAE Visitante</div>
              </div>
            </div>

            {/* Petty cash alert */}
            {match.petty_cash_amount > 0 ? (
              <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-2xl">
                <div className="flex items-center gap-2 text-amber-300 font-black text-sm mb-1">
                  <Sparkles className="w-4 h-4 text-amber-400" />
                  <span>PETTY CASH OTORGADO: {(match.petty_cash_amount).toLocaleString()} mo</span>
                </div>
                <p className="text-xs text-amber-200/80">
                  Beneficiario: <strong className="text-white">
                    {match.petty_cash_team_id === home_team.id ? home_team.name : away_team.name}
                  </strong>. Este saldo es exclusivo para este partido y no se acumula en tesorería.
                </p>
              </div>
            ) : (
              <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl text-center text-xs text-slate-400 font-semibold">
                Ambos equipos tienen la misma VAE. No se otorga Petty Cash.
              </div>
            )}
          </div>

          {/* Incentives Catalog Section */}
          {match.petty_cash_amount > 0 && (
            <div className="bg-slate-900 border border-slate-800 rounded-3xl p-5 shadow-xl space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-base font-black text-white flex items-center gap-2">
                    <ShoppingCart className="w-4 h-4 text-blood-400" />
                    <span>Catálogo de Incentivos</span>
                  </h3>
                  <p className="text-xs text-slate-400">
                    Añade incentivos hasta agotar el saldo de Petty Cash.
                  </p>
                </div>
                <div className="text-right">
                  <span className="text-[10px] text-slate-400 block">Restante</span>
                  <span className={`text-sm font-black ${
                    totalIncentivesCost > match.petty_cash_amount ? 'text-red-400' : 'text-emerald-400'
                  }`}>
                    {(match.petty_cash_amount - totalIncentivesCost).toLocaleString()} mo
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {rulesData?.incentives_catalog?.map((item) => {
                  const qty = selectedIncentives[item.id]?.qty || 0;
                  return (
                    <div
                      key={item.id}
                      className="p-3.5 bg-slate-950 border border-slate-800 rounded-2xl flex items-center justify-between gap-3"
                    >
                      <div className="flex-1">
                        <div className="font-extrabold text-xs text-white leading-tight">{item.name}</div>
                        <div className="text-[10px] text-blood-400 font-bold mt-0.5">
                          {(item.cost).toLocaleString()} mo
                        </div>
                        <div className="text-[10px] text-slate-500 line-clamp-1">{item.description}</div>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          onClick={() => handleUpdateIncentiveQty(item, -1)}
                          disabled={qty === 0}
                          className="w-7 h-7 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-white flex items-center justify-center"
                        >
                          <Minus className="w-3.5 h-3.5" />
                        </button>
                        <span className="font-black text-sm text-white w-4 text-center">{qty}</span>
                        <button
                          onClick={() => handleUpdateIncentiveQty(item, 1)}
                          disabled={qty >= item.max_qty || (totalIncentivesCost + item.cost) > match.petty_cash_amount}
                          className="w-7 h-7 rounded-lg bg-blood-600 hover:bg-blood-500 disabled:opacity-40 text-white flex items-center justify-center"
                        >
                          <Plus className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>

              <button
                onClick={() => handleSaveIncentives(match.petty_cash_team_id)}
                disabled={totalIncentivesCost > match.petty_cash_amount}
                className="w-full py-3 bg-blood-600 hover:bg-blood-500 text-white font-extrabold text-xs uppercase tracking-wider rounded-xl shadow-lg transition"
              >
                Confirmar Compra de Incentivos ({totalIncentivesCost.toLocaleString()} mo)
              </button>
            </div>
          )}

          {/* Pre-Match Rolls Card */}
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-5 shadow-xl space-y-4">
            <h3 className="text-base font-black text-white flex items-center gap-2">
              <Dices className="w-4 h-4 text-blood-400" />
              <span>Tiradas de Prepartido</span>
            </h3>

            {/* Weather Roll (2d6) */}
            <div className="p-4 bg-slate-950 border border-slate-800 rounded-2xl space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-xs font-extrabold text-white">Clima (2D6)</span>
                  <p className="text-[11px] text-slate-400">Determina las condiciones atmosféricas del encuentro.</p>
                </div>
                {match.weather_roll && (
                  <button
                    onClick={() => setActiveRuleModal({
                      title: match.weather_name,
                      subtitle: `Resultado 2D6: ${match.weather_roll}`,
                      content: match.weather_description
                    })}
                    className="px-2.5 py-1 bg-blood-600/20 text-blood-400 border border-blood-500/40 rounded-xl text-xs font-bold hover:bg-blood-600/30"
                  >
                    Ver Regla
                  </button>
                )}
              </div>

              {match.weather_roll ? (
                <div className="p-3 bg-slate-900/80 rounded-xl border border-slate-800 text-xs">
                  <div className="font-black text-white">{match.weather_name} ({match.weather_roll})</div>
                  <div className="text-slate-400 mt-0.5">{match.weather_description}</div>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleRoll('weather')}
                    className="flex-1 py-2.5 bg-blood-600 hover:bg-blood-500 text-white font-bold text-xs rounded-xl shadow transition"
                  >
                    🎲 Tirar Digital (2D6)
                  </button>
                  <div className="flex items-center gap-1 w-28">
                    <input
                      type="number"
                      min={2}
                      max={12}
                      placeholder="Dado"
                      value={manualWeather}
                      onChange={(e) => setManualWeather(e.target.value)}
                      className="w-14 bg-slate-900 border border-slate-700 rounded-xl p-2 text-center text-xs text-white"
                    />
                    <button
                      onClick={() => handleRoll('weather', manualWeather)}
                      disabled={!manualWeather}
                      className="px-2 py-2 bg-slate-800 hover:bg-slate-700 text-white font-bold text-xs rounded-xl"
                    >
                      OK
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Prayers to Nuffle (1d16) */}
            <div className="p-4 bg-slate-950 border border-slate-800 rounded-2xl space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-xs font-extrabold text-white">Plegarias a Nuffle (1D16)</span>
                  <p className="text-[11px] text-slate-400">Favores divinos si se conceden por diferencia de VAE.</p>
                </div>
                {match.prayers_roll && (
                  <button
                    onClick={() => setActiveRuleModal({
                      title: match.prayers_name,
                      subtitle: `Resultado 1D16: ${match.prayers_roll}`,
                      content: match.prayers_description
                    })}
                    className="px-2.5 py-1 bg-blood-600/20 text-blood-400 border border-blood-500/40 rounded-xl text-xs font-bold hover:bg-blood-600/30"
                  >
                    Ver Regla
                  </button>
                )}
              </div>

              {match.prayers_roll ? (
                <div className="p-3 bg-slate-900/80 rounded-xl border border-slate-800 text-xs">
                  <div className="font-black text-white">{match.prayers_name} ({match.prayers_roll})</div>
                  <div className="text-slate-400 mt-0.5">{match.prayers_description}</div>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleRoll('prayers')}
                    className="flex-1 py-2.5 bg-blood-600 hover:bg-blood-500 text-white font-bold text-xs rounded-xl shadow transition"
                  >
                    🎲 Tirar Digital (1D16)
                  </button>
                  <div className="flex items-center gap-1 w-28">
                    <input
                      type="number"
                      min={1}
                      max={16}
                      placeholder="Dado"
                      value={manualPrayers}
                      onChange={(e) => setManualPrayers(e.target.value)}
                      className="w-14 bg-slate-900 border border-slate-700 rounded-xl p-2 text-center text-xs text-white"
                    />
                    <button
                      onClick={() => handleRoll('prayers', manualPrayers)}
                      disabled={!manualPrayers}
                      className="px-2 py-2 bg-slate-800 hover:bg-slate-700 text-white font-bold text-xs rounded-xl"
                    >
                      OK
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Kick-off Table (2d6) */}
            <div className="p-4 bg-slate-950 border border-slate-800 rounded-2xl space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-xs font-extrabold text-white">Patada Inicial (2D6)</span>
                  <p className="text-[11px] text-slate-400">Evento de la patada de inicio de la primera parte.</p>
                </div>
                {match.kick_off_roll && (
                  <button
                    onClick={() => setActiveRuleModal({
                      title: match.kick_off_name,
                      subtitle: `Resultado 2D6: ${match.kick_off_roll}`,
                      content: match.kick_off_description
                    })}
                    className="px-2.5 py-1 bg-blood-600/20 text-blood-400 border border-blood-500/40 rounded-xl text-xs font-bold hover:bg-blood-600/30"
                  >
                    Ver Regla
                  </button>
                )}
              </div>

              {match.kick_off_roll ? (
                <div className="p-3 bg-slate-900/80 rounded-xl border border-slate-800 text-xs">
                  <div className="font-black text-white">{match.kick_off_name} ({match.kick_off_roll})</div>
                  <div className="text-slate-400 mt-0.5">{match.kick_off_description}</div>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleRoll('kick_off')}
                    className="flex-1 py-2.5 bg-blood-600 hover:bg-blood-500 text-white font-bold text-xs rounded-xl shadow transition"
                  >
                    🎲 Tirar Digital (2D6)
                  </button>
                  <div className="flex items-center gap-1 w-28">
                    <input
                      type="number"
                      min={2}
                      max={12}
                      placeholder="Dado"
                      value={manualKick}
                      onChange={(e) => setManualKick(e.target.value)}
                      className="w-14 bg-slate-900 border border-slate-700 rounded-xl p-2 text-center text-xs text-white"
                    />
                    <button
                      onClick={() => handleRoll('kick_off', manualKick)}
                      disabled={!manualKick}
                      className="px-2 py-2 bg-slate-800 hover:bg-slate-700 text-white font-bold text-xs rounded-xl"
                    >
                      OK
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Start Match Button */}
          <button
            onClick={handleStartMatch}
            className="w-full py-4 bg-gradient-to-r from-emerald-600 to-emerald-700 hover:from-emerald-500 hover:to-emerald-600 active:scale-[0.99] text-white font-black text-sm uppercase tracking-wider rounded-2xl shadow-xl shadow-emerald-950 flex items-center justify-center gap-2 transition"
          >
            <Swords className="w-5 h-5" />
            <span>¡Comenzar el Partido! (Pito Inicial)</span>
          </button>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* FASE 3: IN_PROGRESS (LIVE TRACKER A DOS COLUMNAS O TABS CON BOTONES RÁPIDOS) */}
      {/* ------------------------------------------------------------- */}
      {(match.status === 'IN_PROGRESS' || match.status === 'COMPLETED') && (
        <div className="space-y-4">
          {/* STICKY LIVE SCOREBOARD */}
          <div className="sticky top-16 z-30 bg-slate-950/95 backdrop-blur-md border border-slate-800 rounded-3xl p-4 shadow-2xl">
            <div className="flex items-center justify-between gap-2">
              {/* Home Team */}
              <div className="flex-1 text-center sm:text-left">
                <span className="text-[10px] font-bold text-blood-400 uppercase block">Local</span>
                <span className="text-sm font-black text-white truncate block">{home_team.name}</span>
              </div>

              {/* Central Score */}
              <div className="flex items-center gap-2 px-4 py-2 bg-slate-900 border border-slate-800 rounded-2xl shadow-inner">
                <span className="text-3xl font-black text-white">{match.home_td}</span>
                <span className="text-xs font-bold text-slate-500">:</span>
                <span className="text-3xl font-black text-white">{match.away_td}</span>
              </div>

              {/* Away Team */}
              <div className="flex-1 text-center sm:text-right">
                <span className="text-[10px] font-bold text-blood-400 uppercase block">Visitante</span>
                <span className="text-sm font-black text-white truncate block">{away_team.name}</span>
              </div>
            </div>

            {/* Turn & Half Bar */}
            <div className="flex items-center justify-between mt-3 pt-3 border-t border-slate-800/80 text-xs">
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-blood-400" />
                <span className="font-extrabold text-white">
                  {match.current_half}ª Mitad - Turno {match.current_turn}/8
                </span>
              </div>

              {match.status === 'IN_PROGRESS' && (
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleAdvanceTurn}
                    className="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-xl text-xs font-bold transition flex items-center gap-1"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Turno</span>
                  </button>

                  <button
                    onClick={() => setShowCompletionModal(true)}
                    className="px-3 py-1 bg-blood-600 hover:bg-blood-500 text-white rounded-xl text-xs font-black uppercase transition"
                  >
                    Pitar Final
                  </button>
                </div>
              )}
            </div>

            {/* Active Weather Reminder */}
            {match.weather_name && (
              <div className="mt-2 text-[11px] text-slate-400 flex items-center justify-center gap-1.5 bg-slate-900/40 py-1 rounded-lg">
                <span>Clima actual:</span>
                <strong className="text-slate-200">{match.weather_name}</strong>
              </div>
            )}
          </div>

          {/* TEAM TOGGLE TABS (FOR MOBILE SINGLE-THUMB USAGE) */}
          <div className="flex p-1 bg-slate-900 border border-slate-800 rounded-2xl shadow-md">
            <button
              onClick={() => setActiveTeamTab('home')}
              className={`flex-1 py-3 rounded-xl text-xs font-black uppercase transition-all ${
                activeTeamTab === 'home'
                  ? 'bg-blood-600 text-white shadow-lg'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              {home_team.name} ({match.home_td} TD)
            </button>
            <button
              onClick={() => setActiveTeamTab('away')}
              className={`flex-1 py-3 rounded-xl text-xs font-black uppercase transition-all ${
                activeTeamTab === 'away'
                  ? 'bg-blood-600 text-white shadow-lg'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              {away_team.name} ({match.away_td} TD)
            </button>
          </div>

          {/* ACTIVE TEAM PLAYERS LIST WITH BIG TOUCH BUTTONS */}
          <div className="space-y-3">
            <div className="text-xs text-slate-400 flex items-center justify-between px-1">
              <span>Plantilla de {currentTeamObj.name}:</span>
              <span>Pulsa un botón para anotar evento en vivo</span>
            </div>

            {activePlayers.map((player) => {
              const isDead = player.status === 'DEAD';
              const isMng = player.status === 'MNG';

              return (
                <div
                  key={player.id}
                  className={`p-3.5 rounded-2xl border transition-all ${
                    isDead 
                      ? 'bg-red-950/20 border-red-900/30 opacity-60 pointer-events-none'
                      : isMng
                      ? 'bg-amber-950/20 border-amber-800/40 opacity-70 pointer-events-none'
                      : 'bg-slate-900 border-slate-800 shadow-md'
                  }`}
                >
                  {/* Player header */}
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="w-6 h-6 bg-slate-950 border border-slate-800 rounded-lg flex items-center justify-center font-black text-xs text-blood-400 shrink-0">
                        #{player.number}
                      </span>
                      <span className="font-extrabold text-sm text-white">{player.name}</span>
                      <span className="text-[10px] text-slate-400 font-semibold">({player.position})</span>
                    </div>

                    <div className="text-[10px] font-bold text-amber-400 bg-slate-950 px-2 py-0.5 rounded-lg border border-slate-800">
                      {player.spp} SPP
                    </div>
                  </div>

                  {/* QUICK EVENT BUTTONS (MOBILE TOUCH OPTIMIZED) */}
                  {match.status === 'IN_PROGRESS' && (
                    <div className="grid grid-cols-5 gap-1.5 pt-1">
                      {/* Touchdown (+1 Score, +3 SPP) */}
                      <button
                        onClick={() => handleAddEvent(currentTeamObj.id, player.id, 'TD')}
                        className="py-2.5 px-1 bg-emerald-600/20 hover:bg-emerald-600/30 active:scale-95 border border-emerald-500/40 text-emerald-300 font-black text-[11px] rounded-xl flex flex-col items-center justify-center shadow"
                      >
                        <span>+ TD</span>
                        <span className="text-[9px] text-emerald-400 font-normal">+3 SPP</span>
                      </button>

                      {/* Casualty (+2 SPP) */}
                      <button
                        onClick={() => handleAddEvent(currentTeamObj.id, player.id, 'CAS')}
                        className="py-2.5 px-1 bg-red-600/20 hover:bg-red-600/30 active:scale-95 border border-red-500/40 text-red-300 font-black text-[11px] rounded-xl flex flex-col items-center justify-center shadow"
                      >
                        <span>+ Baja</span>
                        <span className="text-[9px] text-red-400 font-normal">+2 SPP</span>
                      </button>

                      {/* Pass (+1 SPP) */}
                      <button
                        onClick={() => handleAddEvent(currentTeamObj.id, player.id, 'PASS')}
                        className="py-2.5 px-1 bg-blue-600/20 hover:bg-blue-600/30 active:scale-95 border border-blue-500/40 text-blue-300 font-black text-[11px] rounded-xl flex flex-col items-center justify-center shadow"
                      >
                        <span>+ Pase</span>
                        <span className="text-[9px] text-blue-400 font-normal">+1 SPP</span>
                      </button>

                      {/* Interception (+2 SPP) */}
                      <button
                        onClick={() => handleAddEvent(currentTeamObj.id, player.id, 'INT')}
                        className="py-2.5 px-1 bg-purple-600/20 hover:bg-purple-600/30 active:scale-95 border border-purple-500/40 text-purple-300 font-black text-[11px] rounded-xl flex flex-col items-center justify-center shadow"
                      >
                        <span>+ Inter</span>
                        <span className="text-[9px] text-purple-400 font-normal">+2 SPP</span>
                      </button>

                      {/* Foul (0 SPP, for Malhechores) */}
                      <button
                        onClick={() => handleAddEvent(currentTeamObj.id, player.id, 'FOUL')}
                        className="py-2.5 px-1 bg-amber-600/20 hover:bg-amber-600/30 active:scale-95 border border-amber-500/40 text-amber-300 font-black text-[11px] rounded-xl flex flex-col items-center justify-center shadow"
                      >
                        <span>+ Falta</span>
                        <span className="text-[9px] text-amber-400 font-normal">Sponsor</span>
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* LIVE EVENT FEED (WITH UNDO) */}
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-5 shadow-xl space-y-3">
            <h4 className="text-sm font-extrabold text-white flex items-center gap-2">
              <Award className="w-4 h-4 text-blood-400" />
              <span>Historial de Eventos del Partido</span>
            </h4>

            {events.length === 0 ? (
              <p className="text-xs text-slate-500 text-center py-4 italic">
                Aún no se han registrado eventos en este partido.
              </p>
            ) : (
              <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                {events.map((ev) => {
                  const evTeam = ev.team_id === home_team.id ? home_team : away_team;
                  const allPlayers = [...home_players, ...away_players];
                  const evPlayer = allPlayers.find(p => p.id === ev.player_id);

                  return (
                    <div
                      key={ev.id}
                      className="p-3 bg-slate-950 border border-slate-800 rounded-xl flex items-center justify-between text-xs"
                    >
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-0.5 rounded font-black text-[10px] ${
                          ev.event_type === 'TD' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' :
                          ev.event_type === 'CAS' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
                          ev.event_type === 'PASS' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' :
                          ev.event_type === 'INT' ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30' :
                          ev.event_type === 'MVP' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
                          'bg-slate-800 text-slate-300'
                        }`}>
                          {ev.event_type}
                        </span>

                        <div>
                          <span className="font-extrabold text-white">
                            {evPlayer ? `${evPlayer.name} (#${evPlayer.number})` : evTeam.name}
                          </span>
                          <span className="text-[10px] text-slate-500 ml-1.5">
                            ({evTeam.name} • {ev.half}ªP Turno {ev.turn})
                          </span>
                        </div>
                      </div>

                      {match.status === 'IN_PROGRESS' && (
                        <button
                          onClick={() => handleDeleteEvent(ev.id)}
                          title="Deshacer evento"
                          className="p-1.5 text-slate-400 hover:text-red-400 bg-slate-900 rounded-lg transition"
                        >
                          <Undo2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* FASE 4: MODAL DE CIERRE DE ACTA (GANANCIAS, MVP, LESIONES, MERCY RULE) */}
      {/* ------------------------------------------------------------- */}
      {showCompletionModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/90 backdrop-blur-md overflow-y-auto">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-lg w-full p-6 shadow-2xl relative space-y-5 my-8">
            <div className="text-center">
              <div className="w-12 h-12 bg-blood-600/20 border border-blood-500/40 rounded-2xl flex items-center justify-center mx-auto mb-2 text-blood-500 shadow-lg">
                <Trophy className="w-6 h-6" />
              </div>
              <h3 className="text-xl font-black text-white">CIERRE DE ACTA DE PARTIDO</h3>
              <p className="text-xs text-slate-400">
                Resultado final: <strong className="text-white">{home_team.name} {match.home_td} - {match.away_td} {away_team.name}</strong>
              </p>
            </div>

            {/* 1. Ganancias de Oro (1d6 x 10k) */}
            <div className="p-4 bg-slate-950 border border-slate-800 rounded-2xl space-y-3">
              <span className="text-xs font-black text-white uppercase block">1. Ganancias de Oro (1D6 x 10.000 mo)</span>
              
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-slate-400 font-bold block mb-1">
                    Dado {home_team.name}
                  </label>
                  <input
                    type="number"
                    min={1}
                    max={6}
                    placeholder="1D6 (1-6)"
                    value={homeWinningsRoll || ''}
                    onChange={(e) => setHomeWinningsRoll(parseInt(e.target.value) || 1)}
                    className="w-full bg-slate-900 border border-slate-700 rounded-xl p-2.5 text-center text-sm font-bold text-white"
                  />
                  <span className="text-[10px] text-amber-400 block mt-1">
                    +{((homeWinningsRoll || 1) * 10000).toLocaleString()} mo
                  </span>
                </div>

                <div>
                  <label className="text-[10px] text-slate-400 font-bold block mb-1">
                    Dado {away_team.name}
                  </label>
                  <input
                    type="number"
                    min={1}
                    max={6}
                    placeholder="1D6 (1-6)"
                    value={awayWinningsRoll || ''}
                    onChange={(e) => setAwayWinningsRoll(parseInt(e.target.value) || 1)}
                    className="w-full bg-slate-900 border border-slate-700 rounded-xl p-2.5 text-center text-sm font-bold text-white"
                  />
                  <span className="text-[10px] text-amber-400 block mt-1">
                    +{((awayWinningsRoll || 1) * 10000).toLocaleString()} mo
                  </span>
                </div>
              </div>
            </div>

            {/* 2. Elección de MVP (+4 SPP) */}
            <div className="p-4 bg-slate-950 border border-slate-800 rounded-2xl space-y-3">
              <span className="text-xs font-black text-white uppercase block">2. Jugador Más Valioso (MVP: +4 SPP)</span>

              <div className="space-y-2">
                <div>
                  <label className="text-[10px] text-slate-400 font-bold block mb-1">MVP {home_team.name}</label>
                  <select
                    value={selectedMvpHomes}
                    onChange={(e) => setSelectedMvpHomes(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700 rounded-xl p-2.5 text-xs text-white"
                  >
                    <option value="">Seleccionar jugador local...</option>
                    {home_players.map((p) => (
                      <option key={p.id} value={p.id}>
                        #{p.number} {p.name} ({p.position})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="text-[10px] text-slate-400 font-bold block mb-1">MVP {away_team.name}</label>
                  <select
                    value={selectedMvpAway}
                    onChange={(e) => setSelectedMvpAway(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700 rounded-xl p-2.5 text-xs text-white"
                  >
                    <option value="">Seleccionar jugador visitante...</option>
                    {away_players.map((p) => (
                      <option key={p.id} value={p.id}>
                        #{p.number} {p.name} ({p.position})
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            {/* 3. Reporte de Lesiones Graves & Mercy Rule */}
            <div className="p-4 bg-slate-950 border border-slate-800 rounded-2xl space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-black text-white uppercase">3. Lesiones Graves y Bajas</span>
                {match.round_number <= 2 && (
                  <span className="px-2 py-0.5 bg-emerald-500/20 text-emerald-400 text-[10px] font-bold rounded-full">
                    Mercy Rule Activa
                  </span>
                )}
              </div>

              {match.round_number <= 2 && (
                <div className="p-2.5 bg-emerald-950/30 border border-emerald-800/40 rounded-xl text-[11px] text-emerald-300">
                  🛡️ <strong>Red de Seguridad de Novatos (Jornada {match.round_number}):</strong> Las bajas permanentes o muertes recibirán indemnización automática a la tesorería (1ª 100%, 2ª 50%, 3ª+ 25%).
                </div>
              )}

              {/* Selector to add injury */}
              <div className="flex gap-2">
                <select
                  id="cas_player_select"
                  className="flex-1 bg-slate-900 border border-slate-700 rounded-xl p-2 text-xs text-white"
                >
                  <option value="">Seleccionar jugador lesionado...</option>
                  {[...home_players, ...away_players].map(p => (
                    <option key={p.id} value={p.id}>
                      #{p.number} {p.name} ({p.position})
                    </option>
                  ))}
                </select>

                <select
                  id="cas_outcome_select"
                  className="w-24 bg-slate-900 border border-slate-700 rounded-xl p-2 text-xs text-white"
                >
                  <option value="MNG">MNG</option>
                  <option value="DEAD">DEAD</option>
                </select>

                <button
                  type="button"
                  onClick={() => {
                    const sel = document.getElementById('cas_player_select');
                    const out = document.getElementById('cas_outcome_select');
                    if (sel.value) {
                      setCasualtiesReport([
                        ...casualtiesReport,
                        { player_id: parseInt(sel.value), outcome: out.value, injury: 'Lesión en partido' }
                      ]);
                      sel.value = '';
                    }
                  }}
                  className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-white font-bold text-xs rounded-xl"
                >
                  + Añadir
                </button>
              </div>

              {casualtiesReport.length > 0 && (
                <div className="space-y-1.5 pt-2">
                  {casualtiesReport.map((c, idx) => {
                    const p = [...home_players, ...away_players].find(pl => pl.id === c.player_id);
                    return (
                      <div key={idx} className="p-2 bg-slate-900 rounded-xl flex items-center justify-between text-xs">
                        <span className="text-white font-semibold">
                          #{p?.number} {p?.name} — <strong className="text-red-400">{c.outcome}</strong>
                        </span>
                        <button
                          onClick={() => setCasualtiesReport(casualtiesReport.filter((_, i) => i !== idx))}
                          className="text-slate-400 hover:text-red-400"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Actions */}
            <div className="flex gap-3 pt-2">
              <button
                type="button"
                onClick={() => setShowCompletionModal(false)}
                className="flex-1 py-3 bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold text-xs uppercase rounded-xl"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleFinalizeMatch}
                className="flex-1 py-3 bg-blood-600 hover:bg-blood-500 text-white font-black text-xs uppercase rounded-xl shadow-lg shadow-blood-950"
              >
                Cerrar y Guardar Acta
              </button>
            </div>
          </div>
        </div>
      )}

      {/* RULE MODAL POPUP */}
      {activeRuleModal && (
        <RuleModal
          isOpen={true}
          onClose={() => setActiveRuleModal(null)}
          title={activeRuleModal.title}
          subtitle={activeRuleModal.subtitle}
          content={activeRuleModal.content}
        />
      )}
    </div>
  );
}
