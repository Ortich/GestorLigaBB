import React, { useState } from 'react';
import { 
  ShieldAlert, RefreshCw, AlertTriangle, Coins, HeartPulse, 
  RotateCcw, Check, X, Shield, Users, Trophy, Calendar
} from 'lucide-react';
import { api } from '../api';

export default function AdminPanel({ 
  isOpen, 
  onClose, 
  masterKey, 
  matches, 
  teams, 
  leagueInfo, 
  onRefreshData 
}) {
  const [selectedMatchId, setSelectedMatchId] = useState(matches[0]?.id || 1);
  const [newStatus, setNewStatus] = useState('IN_PROGRESS');
  const [manualHomeTd, setManualHomeTd] = useState(0);
  const [manualAwayTd, setManualAwayTd] = useState(0);

  const [selectedTeamId, setSelectedTeamId] = useState(teams[0]?.id || 1);
  const [goldAmount, setGoldAmount] = useState(50000);

  const [selectedPlayerTeamId, setSelectedPlayerTeamId] = useState(teams[0]?.id || 1);
  const [teamPlayers, setTeamPlayers] = useState([]);
  const [selectedPlayerId, setSelectedPlayerId] = useState('');
  const [playerStatus, setPlayerStatus] = useState('ACTIVE');
  const [playerSppDelta, setPlayerSppDelta] = useState(0);

  const [advanceRoundNumber, setAdvanceRoundNumber] = useState((leagueInfo?.current_round || 1) + 1);
  const [activeBounty, setActiveBounty] = useState(leagueInfo?.active_bounty_id || 'cazador_de_cabezas');

  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');

  if (!isOpen) return null;

  const showFeedback = (successMsg, isError = false) => {
    if (isError) {
      setErr(successMsg);
      setMsg('');
    } else {
      setMsg(successMsg);
      setErr('');
    }
    setTimeout(() => {
      setMsg('');
      setErr('');
    }, 4000);
  };

  const handleForceStatus = async () => {
    setLoading(true);
    try {
      await api.adminForceStatus(Number(selectedMatchId), newStatus, masterKey);
      showFeedback(`Estado del partido #${selectedMatchId} cambiado a ${newStatus}.`);
      onRefreshData();
    } catch (e) {
      showFeedback(e.message, true);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateScore = async () => {
    setLoading(true);
    try {
      await api.adminUpdateScore(Number(selectedMatchId), Number(manualHomeTd), Number(manualAwayTd), masterKey);
      showFeedback(`Marcador del partido #${selectedMatchId} actualizado a ${manualHomeTd}-${manualAwayTd}.`);
      onRefreshData();
    } catch (e) {
      showFeedback(e.message, true);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateTreasury = async (delta) => {
    setLoading(true);
    try {
      await api.adminUpdateTreasury(Number(selectedTeamId), delta, masterKey);
      showFeedback(`Tesorería actualizada para equipo ID ${selectedTeamId} (${delta > 0 ? `+${delta}` : delta} mo).`);
      onRefreshData();
    } catch (e) {
      showFeedback(e.message, true);
    } finally {
      setLoading(false);
    }
  };

  const loadTeamPlayers = async (teamId) => {
    setSelectedPlayerTeamId(teamId);
    try {
      const data = await api.getTeamDetail(teamId);
      setTeamPlayers(data.players || []);
      if (data.players?.length > 0) {
        setSelectedPlayerId(data.players[0].id);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleUpdatePlayerStatus = async () => {
    if (!selectedPlayerId) return;
    setLoading(true);
    try {
      await api.adminUpdatePlayer(Number(selectedPlayerId), {
        status: playerStatus,
        spp_delta: Number(playerSppDelta)
      }, masterKey);
      showFeedback(`Jugador #${selectedPlayerId} actualizado: Estado ${playerStatus}, SPP delta: ${playerSppDelta}.`);
      onRefreshData();
    } catch (e) {
      showFeedback(e.message, true);
    } finally {
      setLoading(false);
    }
  };

  const handleRecalculate = async () => {
    if (!confirm('¿Seguro que deseas regenerar la tabla de clasificación y reasignar sponsors desde cero?')) {
      return;
    }
    setLoading(true);
    try {
      const res = await api.adminRecalculate(masterKey);
      showFeedback(res.message || 'Clasificación y sponsors recalculados con éxito.');
      onRefreshData();
    } catch (e) {
      showFeedback(e.message, true);
    } finally {
      setLoading(false);
    }
  };

  const handleAdvanceRound = async () => {
    setLoading(true);
    try {
      await api.adminAdvanceRound(Number(advanceRoundNumber), activeBounty, masterKey);
      showFeedback(`Jornada avanzada a Jornada ${advanceRoundNumber}.`);
      onRefreshData();
    } catch (e) {
      showFeedback(e.message, true);
    } finally {
      setLoading(false);
    }
  };

  const selectedMatch = matches.find(m => m.id === Number(selectedMatchId));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/90 backdrop-blur-md overflow-y-auto">
      <div className="bg-slate-900 border border-slate-700 rounded-3xl max-w-xl w-full p-6 shadow-2xl relative space-y-6 my-8">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 text-slate-400 hover:text-white bg-slate-800 rounded-full"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-blood-600/20 border border-blood-500/40 rounded-2xl flex items-center justify-center text-blood-500 shadow-lg">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-xl font-black text-white">PANEL DEL COMISIONADO</h2>
            <p className="text-xs text-slate-400">Control de Actas, Tesorerías, Hospital y Recálculo de Liga</p>
          </div>
        </div>

        {msg && (
          <div className="p-3 bg-emerald-950/70 border border-emerald-800 rounded-xl text-emerald-300 text-xs font-bold flex items-center gap-2">
            <Check className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{msg}</span>
          </div>
        )}

        {err && (
          <div className="p-3 bg-red-950/70 border border-red-800 rounded-xl text-red-300 text-xs font-bold flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
            <span>{err}</span>
          </div>
        )}

        {/* 1. GESTOR DE ACTAS Y PARTIDOS */}
        <div className="p-4 bg-slate-950 border border-slate-800 rounded-2xl space-y-3">
          <h3 className="text-xs font-black uppercase text-white flex items-center gap-2">
            <Trophy className="w-4 h-4 text-blood-400" />
            <span>1. Gestor de Actas y Partidos</span>
          </h3>

          <div>
            <label className="text-[11px] text-slate-400 font-bold block mb-1">Seleccionar Partido</label>
            <select
              value={selectedMatchId}
              onChange={(e) => setSelectedMatchId(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-xl p-2.5 text-xs text-white"
            >
              {matches.map((m) => (
                <option key={m.id} value={m.id}>
                  J{m.round_number} #{m.id}: {m.home_team_name} ({m.home_td}) vs ({m.away_td}) {m.away_team_name} [{m.status}]
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-2 pt-2">
            <div>
              <label className="text-[10px] text-slate-400 font-bold block mb-1">Forzar Estado</label>
              <div className="flex gap-1.5">
                <select
                  value={newStatus}
                  onChange={(e) => setNewStatus(e.target.value)}
                  className="flex-1 bg-slate-900 border border-slate-700 rounded-xl p-2 text-xs text-white"
                >
                  <option value="SCHEDULED">SCHEDULED</option>
                  <option value="READY_CHECK">READY_CHECK</option>
                  <option value="PRE_MATCH">PRE_MATCH</option>
                  <option value="IN_PROGRESS">IN_PROGRESS</option>
                  <option value="COMPLETED">COMPLETED</option>
                </select>
                <button
                  onClick={handleForceStatus}
                  disabled={loading}
                  className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-white font-bold text-xs rounded-xl"
                >
                  Aplicar
                </button>
              </div>
            </div>

            <div>
              <label className="text-[10px] text-slate-400 font-bold block mb-1">Modificar Marcador</label>
              <div className="flex items-center gap-1">
                <input
                  type="number"
                  placeholder="Loc"
                  value={manualHomeTd}
                  onChange={(e) => setManualHomeTd(e.target.value)}
                  className="w-12 bg-slate-900 border border-slate-700 rounded-xl p-2 text-center text-xs text-white"
                />
                <span className="text-slate-500 font-bold">:</span>
                <input
                  type="number"
                  placeholder="Vis"
                  value={manualAwayTd}
                  onChange={(e) => setManualAwayTd(e.target.value)}
                  className="w-12 bg-slate-900 border border-slate-700 rounded-xl p-2 text-center text-xs text-white"
                />
                <button
                  onClick={handleUpdateScore}
                  disabled={loading}
                  className="px-2.5 py-2 bg-slate-800 hover:bg-slate-700 text-white font-bold text-xs rounded-xl"
                >
                  Guardar
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* 2. GESTOR DE TESORERÍA */}
        <div className="p-4 bg-slate-950 border border-slate-800 rounded-2xl space-y-3">
          <h3 className="text-xs font-black uppercase text-white flex items-center gap-2">
            <Coins className="w-4 h-4 text-amber-400" />
            <span>2. Gestor de Tesorería</span>
          </h3>

          <div>
            <label className="text-[11px] text-slate-400 font-bold block mb-1">Equipo</label>
            <select
              value={selectedTeamId}
              onChange={(e) => setSelectedTeamId(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-xl p-2.5 text-xs text-white"
            >
              {teams.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name} ({(t.treasury).toLocaleString()} mo)
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => handleUpdateTreasury(50000)}
              disabled={loading}
              className="flex-1 py-2 bg-emerald-950/60 hover:bg-emerald-900 border border-emerald-800 text-emerald-300 font-bold text-xs rounded-xl"
            >
              +50,000 mo
            </button>
            <button
              onClick={() => handleUpdateTreasury(100000)}
              disabled={loading}
              className="flex-1 py-2 bg-emerald-950/60 hover:bg-emerald-900 border border-emerald-800 text-emerald-300 font-bold text-xs rounded-xl"
            >
              +100,000 mo
            </button>
            <button
              onClick={() => handleUpdateTreasury(-50000)}
              disabled={loading}
              className="flex-1 py-2 bg-red-950/60 hover:bg-red-900 border border-red-800 text-red-300 font-bold text-xs rounded-xl"
            >
              -50,000 mo
            </button>
          </div>
        </div>

        {/* 3. HOSPITAL Y SALUD DE JUGADORES */}
        <div className="p-4 bg-slate-950 border border-slate-800 rounded-2xl space-y-3">
          <h3 className="text-xs font-black uppercase text-white flex items-center gap-2">
            <HeartPulse className="w-4 h-4 text-emerald-400" />
            <span>3. Hospital y Salud de Jugadores (Revivir DEAD / Limpiar MNG)</span>
          </h3>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[10px] text-slate-400 font-bold block mb-1">Equipo</label>
              <select
                value={selectedPlayerTeamId}
                onChange={(e) => loadTeamPlayers(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-xl p-2 text-xs text-white"
              >
                {teams.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-[10px] text-slate-400 font-bold block mb-1">Jugador</label>
              <select
                value={selectedPlayerId}
                onChange={(e) => setSelectedPlayerId(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-xl p-2 text-xs text-white"
              >
                {teamPlayers.length === 0 && <option value="">Selecciona equipo primero...</option>}
                {teamPlayers.map((p) => (
                  <option key={p.id} value={p.id}>
                    #{p.number} {p.name} [{p.status}]
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex items-center gap-2 pt-1">
            <select
              value={playerStatus}
              onChange={(e) => setPlayerStatus(e.target.value)}
              className="w-32 bg-slate-900 border border-slate-700 rounded-xl p-2 text-xs text-white font-bold"
            >
              <option value="ACTIVE">ACTIVO (Revivir)</option>
              <option value="MNG">MNG</option>
              <option value="DEAD">DEAD</option>
            </select>

            <input
              type="number"
              placeholder="Delta SPP"
              value={playerSppDelta}
              onChange={(e) => setPlayerSppDelta(e.target.value)}
              className="w-24 bg-slate-900 border border-slate-700 rounded-xl p-2 text-xs text-white text-center"
            />

            <button
              onClick={handleUpdatePlayerStatus}
              disabled={loading || !selectedPlayerId}
              className="flex-1 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs rounded-xl shadow"
            >
              Aplicar a Jugador
            </button>
          </div>
        </div>

        {/* 4. CONTROL DE JORNADA & BOUNTY */}
        <div className="p-4 bg-slate-950 border border-slate-800 rounded-2xl space-y-3">
          <h3 className="text-xs font-black uppercase text-white flex items-center gap-2">
            <Calendar className="w-4 h-4 text-blue-400" />
            <span>4. Control de Jornada de Liga</span>
          </h3>

          <div className="flex items-center gap-2">
            <input
              type="number"
              min={1}
              max={7}
              value={advanceRoundNumber}
              onChange={(e) => setAdvanceRoundNumber(e.target.value)}
              className="w-20 bg-slate-900 border border-slate-700 rounded-xl p-2 text-xs text-white text-center"
            />
            <input
              type="text"
              placeholder="Bounty Semanal"
              value={activeBounty}
              onChange={(e) => setActiveBounty(e.target.value)}
              className="flex-1 bg-slate-900 border border-slate-700 rounded-xl p-2 text-xs text-white"
            />
            <button
              onClick={handleAdvanceRound}
              disabled={loading}
              className="px-3 py-2 bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs rounded-xl"
            >
              Avanzar
            </button>
          </div>
        </div>

        {/* 5. TRIGGER DE RECÁLCULO (BOTÓN DE PELIGRO) */}
        <div className="p-4 bg-red-950/20 border border-red-900/40 rounded-2xl space-y-3">
          <div className="flex items-center gap-2 text-red-400 font-black text-xs uppercase">
            <AlertTriangle className="w-4 h-4" />
            <span>Zona de Peligro: Recálculo de Clasificación y Sponsors</span>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            Regenera todos los puntos, desempates y la asignación estricta de los 4 sponsors dinámicos leyendo desde cero el historial de eventos de todos los partidos.
          </p>
          <button
            onClick={handleRecalculate}
            disabled={loading}
            className="w-full py-3 bg-red-600 hover:bg-red-500 text-white font-black text-xs uppercase tracking-wider rounded-xl shadow-lg transition flex items-center justify-center gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Recalcular Liga y Sponsors Ahora</span>
          </button>
        </div>
      </div>
    </div>
  );
}
