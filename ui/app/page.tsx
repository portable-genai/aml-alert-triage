"use client";

import { useEffect, useState } from "react";

// Every request goes to THIS origin. The browser never learns the service's address and never
// holds its credential; the route handler under /api/agent forwards, having discarded whatever
// identity the client tried to assert.
const API = "/api/agent";

// Mirrors the service's seeded local personas. The picker is a DEV convenience: the server
// validates the selection against its own list, so a hand-crafted value cannot invent a persona.
const PERSONAS = ["analyst", "approver", "auditor", "other-tenant"];

// What happened to the human-review hand-off, in the words the user needs. A result that
// escalated but is not queued must say so rather than read as reviewed.
const REVIEW_ROUTING_TEXT: Record<string, string> = {
  routed: "Sent to the review console.",
  failed: "Could not reach the review console; this case is not queued for review.",
  off: "Review routing is off in this deployment; this case is not queued for review.",
};

function reviewRoutingOf(body: string): string | undefined {
  try {
    const parsed = JSON.parse(body) as { review_routing?: unknown };
    return typeof parsed.review_routing === "string" ? parsed.review_routing : undefined;
  } catch {
    return undefined;
  }
}

// One row of the tenant's open-alert queue, as `GET /v1/alerts` returns it.
interface AlertSummary {
  alert_id: string;
  subject: string;
  opened: string;
}

interface CardSummary {
  name?: string;
  description?: string;
  skills?: { id: string; name: string }[];
}

export default function Home() {
  const [persona, setPersona] = useState(PERSONAS[0]);
  const [alerts, setAlerts] = useState<AlertSummary[] | null>(null);
  const [queueError, setQueueError] = useState("");
  const [alertId, setAlertId] = useState("");
  const [result, setResult] = useState("");
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [card, setCard] = useState<CardSummary | null>(null);

  // The service names itself, so this UI carries no hardcoded product name to go stale.
  useEffect(() => {
    let live = true;
    fetch(API + "/.well-known/agent-card.json", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : null))
      .then((body) => {
        if (live) setCard(body as CardSummary | null);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);

  // The queue is the persona's own tenant's, so it is re-read whenever the persona changes. The
  // console triages an alert by id and never sends transactions: the feed and the warehouse
  // supply the rows, which is the whole of `TriageRequest`.
  useEffect(() => {
    let live = true;
    setAlerts(null);
    setQueueError("");
    setResult("");
    fetch(API + "/v1/alerts", { cache: "no-store", headers: { "X-Dev-Persona": persona } })
      .then(async (response) => {
        if (!response.ok) throw new Error(response.status + " " + (await response.text()));
        return (await response.json()) as AlertSummary[];
      })
      .then((queue) => {
        if (!live) return;
        setAlerts(queue);
        setAlertId(queue[0]?.alert_id ?? "");
      })
      .catch((error: unknown) => {
        if (live) setQueueError(String(error));
      });
    return () => {
      live = false;
    };
  }, [persona]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setFailed(false);
    try {
      const response = await fetch(API + "/v1/triage", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Dev-Persona": persona },
        body: JSON.stringify({ alert_id: alertId }),
      });
      const body = await response.text();
      setFailed(!response.ok);
      setResult(body);
    } catch (error) {
      setFailed(true);
      setResult(String(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <h1>{card?.name ?? "Agent console"}</h1>
      <p className="sub">
        {card?.description ??
          "Triage an open alert. The decision is deterministic, cited, and routed to a human reviewer."}
      </p>

      <form onSubmit={submit}>
        <fieldset>
          <legend>Who you are</legend>
          <label>
            Seeded dev persona (local profile only; the server resolves identity, not this field)
            <select value={persona} onChange={(event) => setPersona(event.target.value)}>
              {PERSONAS.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
        </fieldset>

        <fieldset>
          <legend>Open alerts</legend>
          {queueError ? <p className="result error">Could not read the alert queue: {queueError}</p> : null}
          {alerts && alerts.length === 0 ? (
            <p className="sub">No open alerts in this persona&apos;s tenant.</p>
          ) : null}
          <label>
            Alert
            <select
              value={alertId}
              disabled={!alerts || alerts.length === 0}
              onChange={(event) => setAlertId(event.target.value)}
            >
              {(alerts ?? []).map((alert) => (
                <option key={alert.alert_id} value={alert.alert_id}>
                  {alert.alert_id}: {alert.subject} (opened {alert.opened})
                </option>
              ))}
            </select>
          </label>
          <button type="submit" disabled={busy || !alertId}>
            {busy ? "Working" : "Triage this alert"}
          </button>
        </fieldset>
      </form>

      {result && REVIEW_ROUTING_TEXT[reviewRoutingOf(result) ?? ""] ? (
        <p className="sub" data-review-routing={reviewRoutingOf(result)}>
          {REVIEW_ROUTING_TEXT[reviewRoutingOf(result) ?? ""]}
        </p>
      ) : null}
      {result ? <pre className={failed ? "result error" : "result"}>{result}</pre> : null}

      <footer>
        Synthetic, obviously fictional data only. Identity is resolved server-side and the
        client-asserted actor is discarded; see ui/README.md for the embedding contract.
      </footer>
    </main>
  );
}
