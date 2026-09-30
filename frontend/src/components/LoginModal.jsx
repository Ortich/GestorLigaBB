import React, { useState } from 'react';
import { Shield, KeyRound, AlertCircle, Users, CheckCircle2 } from 'lucide-react';
import { api } from '../api';

export default function LoginModal({ isOpen, teams, onLoginSuccess, onAdminLoginSuccess }) {
  const [selectedTeamId, setSelectedTeamId] = useState(teams[0]?.id || 1);
  const [pin, setPin] = useState('');
  const [masterKey, setMasterKey] = useState('');
  const [isAdminMode, setIsAdminMode] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleCoachLogin = async (e) => {
    e.preventDefault();
    setError('');
    if (!pin || pin.length !== 4) {
      setError('Introduce un PIN de 4 dígitos.');
      return;
    }
    setLoading(true);
    try {
      const res = await api.loginTeam(Number(selectedTeamId), pin);
      onLoginSuccess(res);
      setPin('');
    } catch (err) {
      setError(err.message || 'Error al iniciar sesión.');
    } finally {
      setLoading(false);
    }
  };

  const handleAdminLogin = async (e) => {
    e.preventDefault();
    setError('');
    if (!masterKey) {
      setError('Introduce la MASTER_KEY del Comisionado.');
      return;
    }
    setLoading(true);
    try {
      const res = await api.loginAdmin(masterKey);
      onAdminLoginSuccess(res, masterKey);
      setMasterKey('');
    } catch (err) {
      setError(err.message || 'Error al validar MASTER_KEY.');
    } finally {
      setLoading(false);
    }
  };

  const selectedTeam = teams.find(t => t.id === Number(selectedTeamId));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/90 backdrop-blur-md">
      <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-sm w-full p-6 shadow-2xl relative">
        <div className="text-center mb-6">
          <div className="w-14 h-14 bg-blood-600/20 border border-blood-500/40 rounded-2xl flex items-center justify-center mx-auto mb-3 text-blood-500 shadow-lg shadow-blood-950">
            {isAdminMode ? <Shield className="w-7 h-7" /> : <KeyRound className="w-7 h-7" />}
          </div>
          <h2 className="text-2xl font-black text-white tracking-wide">
            {isAdminMode ? 'ACCESO COMISIONADO' : 'ACCESO ENTRENADOR'}
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            {isAdminMode ? 'Introduce la Master Key de la Liga' : 'Selecciona tu equipo e introduce tu PIN de 4 dígitos'}
          </p>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-950/70 border border-red-800/80 rounded-xl flex items-center gap-2 text-red-300 text-xs font-semibold">
            <AlertCircle className="w-4 h-4 shrink-0 text-red-400" />
            <span>{error}</span>
          </div>
        )}

        {!isAdminMode ? (
          <form onSubmit={handleCoachLogin} className="space-y-4">
            {/* Team Dropdown / Selector */}
            <div>
              <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                Equipo
              </label>
              <div className="relative">
                <select
                  value={selectedTeamId}
                  onChange={(e) => setSelectedTeamId(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-2xl px-4 py-3.5 text-white text-sm font-semibold focus:outline-none focus:border-blood-500 appearance-none shadow-inner"
                >
                  {teams.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name} ({t.race}) - {t.coach_name}
                    </option>
                  ))}
                </select>
                <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400">
                  <Users className="w-4 h-4" />
                </div>
              </div>
            </div>

            {/* Selected Team Quick Info Card */}
            {selectedTeam && (
              <div className="bg-slate-950/50 border border-slate-800 rounded-xl p-3 flex justify-between items-center text-xs text-slate-300">
                <div>
                  <span className="text-slate-400">Entrenador: </span>
                  <span className="font-bold text-white">{selectedTeam.coach_name}</span>
                </div>
                <div>
                  <span className="text-slate-400">Raza: </span>
                  <span className="font-bold text-blood-400">{selectedTeam.race}</span>
                </div>
              </div>
            )}

            {/* PIN Input */}
            <div>
              <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                PIN de 4 Dígitos
              </label>
              <input
                type="password"
                inputMode="numeric"
                pattern="[0-9]*"
                maxLength={4}
                placeholder="••••"
                value={pin}
                onChange={(e) => setPin(e.target.value.replace(/\D/g, '').slice(0, 4))}
                className="w-full bg-slate-950 border border-slate-700 rounded-2xl px-4 py-3.5 text-center text-2xl font-black tracking-widest text-white focus:outline-none focus:border-blood-500 shadow-inner"
                required
              />
            </div>

            {/* Quick Helper for Demo Testing */}
            <p className="text-[11px] text-center text-slate-500">
              Tip: Equipos 1-8 tienen PIN por defecto: 1111, 2222, 3333...
            </p>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3.5 bg-blood-600 hover:bg-blood-500 active:scale-[0.98] text-white font-extrabold text-sm uppercase tracking-wider rounded-2xl shadow-xl shadow-blood-950/50 transition-all flex items-center justify-center gap-2"
            >
              {loading ? 'Verificando...' : 'Entrar al Banquillo'}
            </button>
          </form>
        ) : (
          <form onSubmit={handleAdminLogin} className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                MASTER_KEY de Comisionado
              </label>
              <input
                type="password"
                placeholder="Introduce la Master Key..."
                value={masterKey}
                onChange={(e) => setMasterKey(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-2xl px-4 py-3.5 text-white text-sm font-semibold focus:outline-none focus:border-blood-500 shadow-inner"
                required
              />
            </div>

            <p className="text-[11px] text-center text-slate-500">
              Master Key por defecto: <code className="text-slate-400 bg-slate-800 px-1 py-0.5 rounded">bbmaster2026</code>
            </p>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3.5 bg-amber-600 hover:bg-amber-500 active:scale-[0.98] text-slate-950 font-extrabold text-sm uppercase tracking-wider rounded-2xl shadow-xl transition-all flex items-center justify-center gap-2"
            >
              {loading ? 'Accediendo...' : 'Abrir Panel Comisionado'}
            </button>
          </form>
        )}

        {/* Toggle Mode */}
        <div className="mt-6 pt-4 border-t border-slate-800/80 text-center">
          <button
            type="button"
            onClick={() => {
              setIsAdminMode(!isAdminMode);
              setError('');
            }}
            className="text-xs text-slate-400 hover:text-blood-400 font-semibold underline underline-offset-4 transition"
          >
            {isAdminMode ? 'Volver al Login de Entrenador' : '¿Eres el Comisionado de la Liga? Entrar aquí'}
          </button>
        </div>
      </div>
    </div>
  );
}
