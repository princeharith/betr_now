import { useEffect, useState } from "react";
import { marketOddsUrl, placeBet, resolveMarket } from "./api";

export default function MarketDetail({ market, currentUserId, onAction }) {
  // Seed odds from the market's pools (yes_price = pool_no / total — same
  // formula as amm.py's get_prices). The WebSocket takes over from here.
  const total = market.pool_yes + market.pool_no;
  const [odds, setOdds] = useState({
    yes_price: market.pool_no / total,
    no_price: market.pool_yes / total,
  });
  const [side, setSide] = useState("yes");
  const [amount, setAmount] = useState(10);
  const [error, setError] = useState(null);
  const [lastBet, setLastBet] = useState(null);

  // Browser-side mirror of market_odds_feed() on the server: open a socket
  // for THIS market, update state on every push, close on navigate-away
  // (the cleanup function) — which makes the server handler unsubscribe
  // from the Redis channel.
  useEffect(() => {
    const ws = new WebSocket(marketOddsUrl(market.id));
    ws.onmessage = (event) => {
      setOdds(JSON.parse(event.data));
    };
    return () => ws.close();
  }, [market.id]);

  const bet = async () => {
    setError(null);
    try {
      const result = await placeBet(currentUserId, market.id, side, Number(amount));
      setLastBet(result);
      onAction();
    } catch (e) {
      setError(e.message);
    }
  };

  const resolve = async (outcome) => {
    setError(null);
    try {
      await resolveMarket(market.id, outcome);
      onAction();
    } catch (e) {
      setError(e.message);
    }
  };

  const pct = (p) => `${(p * 100).toFixed(1)}%`;
  const resolved = market.status === "resolved";

  return (
    <div className="card detail">
      <div className="detail-head">
        <div>
          <h2>{market.title}</h2>
          {market.description && <p className="muted">{market.description}</p>}
        </div>
        {!resolved && (
          <span className="live-badge">
            <span className="live-dot" />
            LIVE
          </span>
        )}
      </div>

      <div className="odds">
        <div
          className={`odds-box yes ${side === "yes" ? "active" : ""}`}
          onClick={() => setSide("yes")}
        >
          <span className="odds-label">YES</span>
          <span className="odds-value">{pct(odds.yes_price)}</span>
        </div>
        <div
          className={`odds-box no ${side === "no" ? "active" : ""}`}
          onClick={() => setSide("no")}
        >
          <span className="odds-label">NO</span>
          <span className="odds-value">{pct(odds.no_price)}</span>
        </div>
      </div>

      <div className="prob-bar">
        <div className="prob-fill" style={{ width: pct(odds.yes_price) }} />
      </div>

      {resolved ? (
        <p className="resolved-banner">
          Resolved — <strong>{market.outcome?.toUpperCase()} won</strong>
        </p>
      ) : (
        <>
          <div className="bet-row">
            <input
              type="number"
              min="1"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
            <button className="bet-btn" onClick={bet}>
              Bet ${amount} on {side.toUpperCase()}
            </button>
          </div>

          <div className="resolve-row">
            <span className="muted">Resolve:</span>
            <button onClick={() => resolve("yes")}>YES won</button>
            <button onClick={() => resolve("no")}>NO won</button>
          </div>
        </>
      )}

      {lastBet && (
        <p className="receipt">
          ✓ Got {lastBet.shares.toFixed(2)} {lastBet.side.toUpperCase()} shares
          at ${lastBet.price.toFixed(3)} avg — pays $
          {lastBet.shares.toFixed(2)} if {lastBet.side.toUpperCase()} wins
        </p>
      )}
      {error && <p className="error">{error}</p>}
    </div>
  );
}
