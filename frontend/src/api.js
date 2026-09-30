const API_BASE = '/api';

export const api = {
  // Rules & League
  async getRules() {
    const res = await fetch(`${API_BASE}/rules`);
    if (!res.ok) throw new Error('Error al cargar las reglas.');
    return res.json();
  },

  async getLeague() {
    const res = await fetch(`${API_BASE}/league`);
    if (!res.ok) throw new Error('Error al cargar el estado de la liga.');
    return res.json();
  },

  // Auth
  async loginTeam(team_id, pin) {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ team_id, pin }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error en el login.');
    return data;
  },

  async loginAdmin(master_key) {
    const res = await fetch(`${API_BASE}/auth/admin`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ master_key }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Clave de comisionado incorrecta.');
    return data;
  },

  // Teams
  async getTeams() {
    const res = await fetch(`${API_BASE}/teams`);
    if (!res.ok) throw new Error('Error al listar equipos.');
    return res.json();
  },

  async getTeamDetail(team_id) {
    const res = await fetch(`${API_BASE}/teams/${team_id}`);
    if (!res.ok) throw new Error('Error al cargar detalle del equipo.');
    return res.json();
  },

  async hirePlayer(team_id, playerData) {
    const res = await fetch(`${API_BASE}/teams/${team_id}/players`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(playerData),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al contratar jugador.');
    return data;
  },

  async firePlayer(player_id) {
    const res = await fetch(`${API_BASE}/players/${player_id}`, {
      method: 'DELETE',
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al despedir jugador.');
    return data;
  },

  // Matches
  async getMatches(round_number = null, team_id = null) {
    const params = new URLSearchParams();
    if (round_number) params.append('round_number', round_number);
    if (team_id) params.append('team_id', team_id);
    const res = await fetch(`${API_BASE}/matches?${params.toString()}`);
    if (!res.ok) throw new Error('Error al obtener partidos.');
    return res.json();
  },

  async getMatchDetail(match_id) {
    const res = await fetch(`${API_BASE}/matches/${match_id}`);
    if (!res.ok) throw new Error('Error al obtener detalle del partido.');
    return res.json();
  },

  async readyCheck(match_id, team_id, pin) {
    const res = await fetch(`${API_BASE}/matches/${match_id}/ready-check`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ team_id, pin }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error en Ready Check.');
    return data;
  },

  async buyIncentives(match_id, team_id, incentives) {
    const res = await fetch(`${API_BASE}/matches/${match_id}/incentives`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ team_id, incentives }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al comprar incentivos.');
    return data;
  },

  async rollDice(match_id, roll_type, roll_value = null) {
    const res = await fetch(`${API_BASE}/matches/${match_id}/roll`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ roll_type, roll_value }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al realizar tirada.');
    return data;
  },

  async startMatch(match_id) {
    const res = await fetch(`${API_BASE}/matches/${match_id}/start`, {
      method: 'POST',
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al iniciar partido.');
    return data;
  },

  async updateTurn(match_id, turn, half) {
    const res = await fetch(`${API_BASE}/matches/${match_id}/turn`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ turn, half }),
    });
    return res.json();
  },

  async addMatchEvent(match_id, eventData) {
    const res = await fetch(`${API_BASE}/matches/${match_id}/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(eventData),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al registrar evento.');
    return data;
  },

  async deleteMatchEvent(match_id, event_id) {
    const res = await fetch(`${API_BASE}/matches/${match_id}/events/${event_id}`, {
      method: 'DELETE',
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al borrar evento.');
    return data;
  },

  async completeMatch(match_id, completionData) {
    const res = await fetch(`${API_BASE}/matches/${match_id}/complete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(completionData),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al finalizar partido.');
    return data;
  },

  // Admin Endpoints
  async adminForceStatus(match_id, new_status, master_key) {
    const res = await fetch(`${API_BASE}/admin/matches/${match_id}/force-status`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-master-key': master_key,
      },
      body: JSON.stringify({ status: new_status }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al forzar estado.');
    return data;
  },

  async adminUpdateScore(match_id, home_td, away_td, master_key) {
    const res = await fetch(`${API_BASE}/admin/matches/${match_id}/update-score`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-master-key': master_key,
      },
      body: JSON.stringify({ home_td, away_td }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al modificar marcador.');
    return data;
  },

  async adminUpdateTreasury(team_id, amount, master_key) {
    const res = await fetch(`${API_BASE}/admin/teams/${team_id}/treasury`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-master-key': master_key,
      },
      body: JSON.stringify({ amount }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al actualizar tesorería.');
    return data;
  },

  async adminUpdatePlayer(player_id, updateData, master_key) {
    const res = await fetch(`${API_BASE}/admin/players/${player_id}/status`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-master-key': master_key,
      },
      body: JSON.stringify(updateData),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al actualizar jugador.');
    return data;
  },

  async adminRecalculate(master_key) {
    const res = await fetch(`${API_BASE}/admin/recalculate`, {
      method: 'POST',
      headers: {
        'x-master-key': master_key,
      },
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al recalcular liga.');
    return data;
  },

  async adminAdvanceRound(round_number, active_bounty_id, master_key) {
    const res = await fetch(`${API_BASE}/admin/league/advance-round`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-master-key': master_key,
      },
      body: JSON.stringify({ round_number, active_bounty_id }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al avanzar jornada.');
    return data;
  },
};
