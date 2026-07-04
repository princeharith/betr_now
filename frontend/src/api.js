// Single place for how the frontend reaches the backend. The browser talks
// to FastAPI at :8000 while Vite serves this app at :5173 — a cross-origin
// request, which only works because of the CORSMiddleware in app/main.py.
const API = "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json();
  if (!res.ok) {
    // FastAPI errors arrive as {"detail": "..."} — surface that message.
    throw new Error(data.detail || `Request failed (${res.status})`);
  }
  return data;
}

export const getUsers = () => request("/users");
export const createUser = (username, displayName) =>
  request("/users", {
    method: "POST",
    body: JSON.stringify({ username, display_name: displayName }),
  });

export const getMarkets = () => request("/markets");
export const createMarket = (title, creatorId) =>
  request("/markets", {
    method: "POST",
    body: JSON.stringify({ title, creator_id: creatorId }),
  });
export const resolveMarket = (marketId, outcome) =>
  request(`/markets/${marketId}/resolve`, {
    method: "POST",
    body: JSON.stringify({ outcome }),
  });

export const placeBet = (userId, marketId, side, amount) =>
  request("/bets", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, market_id: marketId, side, amount }),
  });

export const getPositions = (userId) => request(`/positions/${userId}`);
export const getLeaderboard = () => request("/leaderboard");
export const getSettlement = () => request("/settlement");

// The WebSocket endpoint from app/api/websocket.py — ws:// not http://.
export const marketOddsUrl = (marketId) =>
  `ws://localhost:8000/ws/markets/${marketId}`;
