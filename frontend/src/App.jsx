import React, { useState, useEffect } from 'react';
import { api } from './api';
import Navbar from './components/Navbar';
import Dashboard from './components/Dashboard';
import MatchAssistant from './components/MatchAssistant';
import LoginModal from './components/LoginModal';
import AdminPanel from './components/AdminPanel';

export default function App() {
  const [teams, setTeams] = useState([]);
  const [activeTeam, setActiveTeam] = useState(null);
  const [teamDetail, setTeamDetail] = useState(null);
  const [leagueInfo, setLeagueInfo] = useState(null);
  const [matches, setMatches] = useState([]);
  const [rulesData, setRulesData] = useState(null);

  const [activeMatchId, setActiveMatchId] = useState(null);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [showAdminPanel, setShowAdminPanel] = useState(false);
  const [adminMasterKey, setAdminMasterKey] = useState('bbmaster2026');

  const [loading, setLoading] = useState(true);

  // Initial Data Fetch
  const loadInitialData = async () => {
    try {
      setLoading(true);
      const [teamsData, leagueData, matchesData, rules] = await Promise.all([
        api.getTeams(),
        api.getLeague(),
        api.getMatches(),
        api.getRules()
      ]);
      setTeams(teamsData);
      setLeagueInfo(leagueData);
      setMatches(matchesData);
      setRulesData(rules);

      // Check stored team session
      const savedTeamId = localStorage.getItem('bb_team_id');
      if (savedTeamId) {
        const found = teamsData.find(t => t.id === Number(savedTeamId));
        if (found) {
          setActiveTeam(found);
          const detail = await api.getTeamDetail(found.id);
          setTeamDetail(detail);
        } else {
          setShowLoginModal(true);
        }
      } else {
        setShowLoginModal(true);
      }
    } catch (err) {
      console.error('Error loading initial data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadInitialData();
  }, []);

  const refreshAppData = async () => {
    try {
      const [teamsData, leagueData, matchesData] = await Promise.all([
        api.getTeams(),
        api.getLeague(),
        api.getMatches()
      ]);
      setTeams(teamsData);
      setLeagueInfo(leagueData);
      setMatches(matchesData);

      if (activeTeam) {
        const detail = await api.getTeamDetail(activeTeam.id);
        setTeamDetail(detail);
      }
    } catch (err) {
      console.error('Error refreshing app data:', err);
    }
  };

  const handleCoachLoginSuccess = async (loginData) => {
    localStorage.setItem('bb_team_id', loginData.team_id);
    const found = teams.find(t => t.id === loginData.team_id);
    setActiveTeam(found || { id: loginData.team_id, name: loginData.team_name, coach_name: loginData.coach_name, race: loginData.race });
    const detail = await api.getTeamDetail(loginData.team_id);
    setTeamDetail(detail);
    setShowLoginModal(false);
  };

  const handleAdminLoginSuccess = (adminData, masterKey) => {
    setAdminMasterKey(masterKey);
    setShowLoginModal(false);
    setShowAdminPanel(true);
  };

  const handleLogout = () => {
    localStorage.removeItem('bb_team_id');
    setActiveTeam(null);
    setTeamDetail(null);
    setActiveMatchId(null);
    setShowLoginModal(true);
  };

  const handleHirePlayer = async (teamId, playerData) => {
    try {
      await api.hirePlayer(teamId, playerData);
      await refreshAppData();
    } catch (err) {
      alert(err.message || 'Error al contratar jugador.');
    }
  };

  if (loading && !leagueInfo) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-4">
        <div className="w-12 h-12 border-4 border-blood-600 border-t-transparent rounded-full animate-spin mb-4" />
        <h2 className="text-lg font-black text-white tracking-wider">LIGA BLOOD BOWL BB2020</h2>
        <p className="text-xs text-slate-500 mt-1">Cargando reglamento, equipos y jornadas...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Top Navigation */}
      <Navbar
        activeTeam={activeTeam}
        leagueState={leagueInfo}
        onLogout={handleLogout}
        onOpenAdmin={() => setShowAdminPanel(true)}
      />

      {/* Main Content Area */}
      <main className="flex-1">
        {activeMatchId ? (
          <MatchAssistant
            matchId={activeMatchId}
            rulesData={rulesData}
            onBack={() => {
              setActiveMatchId(null);
              refreshAppData();
            }}
            onMatchUpdated={refreshAppData}
          />
        ) : (
          <Dashboard
            teamDetail={teamDetail}
            leagueInfo={leagueInfo}
            matches={matches}
            onOpenMatch={(matchId) => setActiveMatchId(matchId)}
            onRefresh={refreshAppData}
            onHirePlayer={handleHirePlayer}
          />
        )}
      </main>

      {/* Modals */}
      <LoginModal
        isOpen={showLoginModal}
        teams={teams}
        onLoginSuccess={handleCoachLoginSuccess}
        onAdminLoginSuccess={handleAdminLoginSuccess}
      />

      <AdminPanel
        isOpen={showAdminPanel}
        onClose={() => setShowAdminPanel(false)}
        masterKey={adminMasterKey}
        matches={matches}
        teams={teams}
        leagueInfo={leagueInfo}
        onRefreshData={refreshAppData}
      />
    </div>
  );
}
