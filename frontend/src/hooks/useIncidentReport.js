import { useState } from "react";

/**
 * Anonymous incident reporter — submits a SHA-256 hash of the incident to the
 * backend, which signs and submits a Solana memo transaction (devnet) on the
 * user's behalf.  The user never needs SOL; the backend wallet pays the fee.
 *
 * This satisfies the Superteam Solana requirement: on-chain proof of data
 * integrity without forcing users to fund a wallet.
 */

async function hashIncident(data) {
  const encoded = new TextEncoder().encode(JSON.stringify(data));
  const buf = await crypto.subtle.digest("SHA-256", encoded);
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export function useIncidentReport() {
  const [status, setStatus] = useState("idle"); // idle | submitting | done | error
  const [txSignature, setTxSignature] = useState(null);
  const [error, setError] = useState(null);

  const submitIncident = async ({ type, description, lat, lng }) => {
    setStatus("submitting");
    setTxSignature(null);
    setError(null);

    try {
      const payload = {
        app: "belfast-safe",
        type,
        description: description || "",
        lat: lat ? lat.toFixed(5) : null,
        lng: lng ? lng.toFixed(5) : null,
        ts: new Date().toISOString(),
      };
      const hash = await hashIncident(payload);

      // Send to backend — it signs & submits the Solana memo tx with its own wallet
      const res = await fetch("/api/incident/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ hash, payload }),
      });

      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(errBody.detail || `Server error ${res.status}`);
      }

      const result = await res.json();
      setTxSignature(result.signature);
      setStatus("done");
      return result.signature;
    } catch (e) {
      setError(e.message || "Failed to submit incident");
      setStatus("error");
      throw e;
    }
  };

  const reset = () => {
    setStatus("idle");
    setTxSignature(null);
    setError(null);
  };

  const explorerUrl = txSignature
    ? `https://explorer.solana.com/tx/${txSignature}?cluster=devnet`
    : null;

  return { status, txSignature, explorerUrl, error, submitIncident, reset };
}

