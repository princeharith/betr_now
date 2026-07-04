import { useCallback, useEffect, useState } from "react";
import {
  createMarket,
  createUser,
  getLeaderboard,
  getMarkets,
  getPositions,
  getSettlement,
  getUsers,
} from "./api";
import MarketDetail from "./MarketDetail";

export default function App() {
  const [users, setUsers] = useState([]);
  const [currentUserId, setCurrentUserId] = useState(null);
  const [markets, setMarkets] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [leaderboard, setLeaderboard] = useState([]);
  const [positions, setPositions] = useState([]);
  const [settlement, setSettlement] = useState({ payments: [], open_markets: 0 });
  const [newUsername, setNewUsername] = useState("");
  const [newMarketTitle, setNewMarketTitle] = useState("");
  const [error, setError] = useState(null);

  // One refresh function that re-pulls everything. Passed down to
  // MarketDetail so a bet/resolve there updates balances everywhere.
  const refresh = useCallback(async () => {
    const [u, m, lb, s] = await Promise.all([
      getUsers(),
      getMarkets(),
      getLeaderboard(),
      getSettlement(),
    ]);
    setUsers(u);
    setMarkets(m);
    setLeaderboard(lb);
    setSettlement(s);
  }, []);

  useEffect(() => {
    refresh().catch((e) => setError(e.message));
  }, [refresh]);

  // Re-fetch positions whenever the acting user changes or data refreshes.
  useEffect(() => {
    if (currentUserId) {
      getPositions(currentUserId).then(setPositions).catch(() => {});
    } else {
      setPositions([]);
    }
  }, [currentUserId, users]);

  const addUser = async () => {
    setError(null);
    try {
      const u = await createUser(newUsername, newUsername);
      setNewUsername("");
      await refresh();
      setCurrentUserId(u.id);
    } catch (e) {
      setError(e.message);
    }
  };

  const addMarket = async () => {
    setError(null);
    try {
      const m = await createMarket(newMarketTitle, currentUserId);
      setNewMarketTitle("");
      await refresh();
      setSelectedId(m.id);
    } catch (e) {
      setError(e.message);
    }
  };

  const currentUser = users.find((u) => u.id === currentUserId);
  const selected = markets.find((m) => m.id === selectedId);
  const impliedYes = (m) =>
    ((m.pool_no / (m.pool_yes + m.pool_no)) * 100).toFixed(0);
  const openMarkets = markets.filter((m) => m.status !== "resolved");
  const resolvedMarkets = markets.filter((m) => m.status === "resolved");

  const marketRow = (m) => (
    <div
      key={m.id}
      className={`card market-row ${m.id === selectedId ? "selected" : ""} ${m.status === "resolved" ? "muted" : ""}`}
      onClick={() => setSelectedId(m.id)}
    >
      <span>{m.title}</span>
      <span className="chip">
        {m.status === "resolved"
          ? `${m.outcome?.toUpperCase()} won`
          : `YES ${impliedYes(m)}%`}
      </span>
    </div>
  );

  return (
    <div className="layout">
      <header>
        <h1>BetrNow</h1>
        <div className="user-picker">
          <select
            value={currentUserId ?? ""}
            onChange={(e) => setCurrentUserId(Number(e.target.value) || null)}
          >
            <option value="">— acting as —</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.username} (${u.balance.toFixed(2)})
              </option>
            ))}
          </select>
          <input
            placeholder="new username"
            value={newUsername}
            onChange={(e) => setNewUsername(e.target.value)}
          />
          <button onClick={addUser} disabled={!newUsername}>
            Join
          </button>
        </div>
      </header>

      {error && <p className="error">{error}</p>}

      <div className="columns">
        <div className="col">
          <h2>Markets</h2>
          {currentUser && (
            <div className="new-market">
              <input
                placeholder="Will Jake leave before midnight?"
                value={newMarketTitle}
                onChange={(e) => setNewMarketTitle(e.target.value)}
              />
              <button onClick={addMarket} disabled={!newMarketTitle}>
                Create
              </button>
            </div>
          )}
          {openMarkets.map(marketRow)}
          {openMarkets.length === 0 && (
            <p className="empty">No open markets — create one.</p>
          )}

          {resolvedMarkets.length > 0 && (
            <>
              <h2 style={{ marginTop: 24 }}>Resolved</h2>
              {resolvedMarkets.map(marketRow)}
            </>
          )}
        </div>

        <div className="col">
          {selected && currentUser ? (
            <MarketDetail
              // key forces a fresh component (and fresh WebSocket) per market
              key={selected.id}
              market={selected}
              currentUserId={currentUserId}
              onAction={refresh}
            />
          ) : (
            <p className="empty">
              {currentUser
                ? "Pick a market to see live odds."
                : "Join or select a user to start betting."}
            </p>
          )}

          {currentUser && positions.length > 0 && (
            <div className="card">
              <h3>Your positions</h3>
              {positions.map((p, i) => (
                <div key={i} className="pos-row">
                  <span>
                    market #{p.market_id} — {p.side.toUpperCase()}
                  </span>
                  <span>
                    {p.shares.toFixed(2)} sh @ ${p.avg_price.toFixed(3)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="col narrow">
          <h2>Leaderboard</h2>
          <div className="card leaderboard">
            {leaderboard.map((u, i) => {
              const delta = u.balance - 100; // vs. starting play-money stake
              return (
                <div
                  key={u.id}
                  className={`lb-row ${u.id === currentUserId ? "me" : ""}`}
                >
                  <span className={`rank r${i + 1}`}>{i + 1}</span>
                  <span className="lb-name">{u.username}</span>
                  <span className="lb-right">
                    <span className="lb-balance">${u.balance.toFixed(2)}</span>
                    {delta !== 0 && (
                      <span className={`lb-delta ${delta > 0 ? "up" : "down"}`}>
                        {delta > 0 ? "+" : ""}
                        {delta.toFixed(2)}
                      </span>
                    )}
                  </span>
                </div>
              );
            })}
            {leaderboard.length === 0 && (
              <p className="empty">No players yet.</p>
            )}
          </div>

          <h2 style={{ marginTop: 24 }}>Settle up</h2>
          <div className="card leaderboard">
            {settlement.payments.map((p, i) => {
              const mine =
                currentUser &&
                (p.from_username === currentUser.username ||
                  p.to_username === currentUser.username);
              return (
                <div key={i} className={`lb-row ${mine ? "me" : ""}`}>
                  <span className="lb-name">
                    {p.from_username} <span className="pay-arrow">→</span>{" "}
                    {p.to_username}
                  </span>
                  <span className="lb-balance">${p.amount.toFixed(2)}</span>
                </div>
              );
            })}
            {settlement.payments.length === 0 && (
              <p className="empty">All square — nothing owed.</p>
            )}
            {settlement.open_markets > 0 && (
              <p className="settle-note">
                {settlement.open_markets} market
                {settlement.open_markets > 1 ? "s" : ""} still open — amounts
                will change
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
