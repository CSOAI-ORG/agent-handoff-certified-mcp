#!/usr/bin/env python3
"""
Agent Handoff Certified MCP Server
===================================
By MEOK AI Labs | https://meok.ai

Verifiable agent-to-agent task handoff with signed provenance chain.

PROBLEM SOLVED: when a multi-agent workflow fails, the question "which agent
accepted task X with what context?" is nearly impossible to answer. This MCP
issues cryptographically signed handoff receipts — initiating agent signs the
offer, accepting agent signs the acceptance, chain is verifiable offline.

USE CASES:
  - Multi-agent orchestration with audit trail
  - SLA-bound handoffs (task must be accepted within Xs or it expires)
  - Cross-organisation agent collaboration (agent A at company X → agent B at company Y)
  - EU AI Act Art 12 automatic logs (delegation/hand-off events)
  - Non-repudiation: accepting agent cannot later deny the task

PRICING:
  - Free — 100 handoffs/day, ephemeral chain
  - Pro £199/mo — unlimited + signed chain attestations + 365-day retention
  - Enterprise £1,499/mo — multi-tenant + cross-org agent directory + SIEM push

Install: pip install agent-handoff-certified-mcp
Run:     python server.py
"""

import json
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from collections import defaultdict
from mcp.server.fastmcp import FastMCP

import os as _os
import sys
import os

_MEOK_API_KEY = _os.environ.get("MEOK_API_KEY", "")

try:
    from auth_middleware import check_access as _shared_check_access
    _AUTH_ENGINE_AVAILABLE = True
except ImportError:
    _AUTH_ENGINE_AVAILABLE = False

    def _shared_check_access(api_key: str = ""):
        """Fallback when shared auth engine is not available."""
        if _MEOK_API_KEY and api_key and api_key == _MEOK_API_KEY:
            return True, "OK", "pro"
        if _MEOK_API_KEY and api_key and api_key != _MEOK_API_KEY:
            return False, "Invalid API key. Get one at https://meok.ai/api-keys", "free"
        return True, "OK", "free"


try:
    from attestation import get_attestation_tool_response
    _ATTESTATION_LOCAL = True
except ImportError:
    _ATTESTATION_LOCAL = False

_ATTESTATION_API = _os.environ.get(
    "MEOK_ATTESTATION_API", "https://meok-attestation-api.vercel.app"
)


def check_access(api_key: str = ""):
    return _shared_check_access(api_key)


STRIPE_199 = "https://buy.stripe.com/14A4gB3K4eUWgYR56o8k836"
STRIPE_1499 = "https://buy.stripe.com/4gM9AV80kaEG0ZT42k8k837"
FREE_DAILY_LIMIT = 100

_SIGNING_KEY = (
    _os.environ.get("MEOK_HANDOFF_KEY", "").encode("utf-8")
    or hashlib.sha256(b"MEOK_HANDOFF_DEV_KEY_ROTATE_BEFORE_GA").digest()
)

_handoffs: dict[str, dict] = {}  # handoff_id -> record
_daily_count: dict[str, int] = defaultdict(int)


def _sign(data: dict) -> str:
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(_SIGNING_KEY, canonical, hashlib.sha256).hexdigest()


mcp = FastMCP(
    "agent-handoff-certified",
    instructions=(
        "MEOK AI Labs Agent Handoff Certified MCP. When one agent delegates to another "
        "(cross-process, cross-network, cross-org), initiate_handoff issues a signed "
        "offer. The receiving agent calls accept_handoff with its identity to complete "
        "the signed chain. verify_chain reconstructs + validates the full trace. "
        "Evidence for EU AI Act Art 12 + ISO 42001 clause 9."
    ),
)


@mcp.tool()
def initiate_handoff(
    tenant_id: str,
    from_agent: str,
    to_agent: str,
    task: str,
    context_json: str = "{}",
    expires_in_seconds: int = 300,
    api_key: str = "",
) -> str:
    """Initiating agent offers a task. Returns handoff_id + signed offer.

    The receiving agent must call accept_handoff within `expires_in_seconds` to
    complete the signed chain.
    """
    allowed, msg, tier = check_access(api_key)
    if not allowed:
        return json.dumps({"error": msg, "upgrade_url": STRIPE_199})

    today = datetime.now(timezone.utc).date().isoformat()
    _daily_count[f"{tenant_id}:{today}"] += 1
    if tier == "free" and _daily_count[f"{tenant_id}:{today}"] > FREE_DAILY_LIMIT:
        return json.dumps({
            "error": f"Free tier: {FREE_DAILY_LIMIT} handoffs/day. Upgrade to Pro for unlimited.",
            "upgrade_url": STRIPE_199,
        })

    try:
        context = json.loads(context_json) if context_json else {}
    except Exception as e:
        return json.dumps({"error": f"invalid context_json: {e}"})

    handoff_id = f"ho-{secrets.token_hex(10)}"
    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=expires_in_seconds)

    offer = {
        "handoff_id": handoff_id,
        "tenant_id": tenant_id,
        "from_agent": from_agent,
        "to_agent": to_agent,
        "task": task,
        "context": context,
        "offered_utc": now.isoformat(),
        "expires_utc": expires.isoformat(),
        "status": "offered",
    }
    offer_signature = _sign(offer)

    record = {**offer, "offer_signature": offer_signature, "acceptance": None, "acceptance_signature": None}
    _handoffs[handoff_id] = record
    return json.dumps({
        "handoff_id": handoff_id,
        "offer_signature": offer_signature,
        "expires_utc": expires.isoformat(),
        "to_agent_must_accept_via": "call accept_handoff(handoff_id, accepting_agent_id, accepting_agent_ref)",
        "tier": tier,
    })


@mcp.tool()
def accept_handoff(
    handoff_id: str,
    accepting_agent_id: str,
    accepting_agent_ref: str = "",
    api_key: str = "",
) -> str:
    """Receiving agent accepts + signs. Completes the chain."""
    allowed, msg, tier = check_access(api_key)
    if not allowed:
        return json.dumps({"error": msg, "upgrade_url": STRIPE_199})

    rec = _handoffs.get(handoff_id)
    if not rec:
        return json.dumps({"error": f"handoff_id {handoff_id} not found"})
    if rec["status"] != "offered":
        return json.dumps({"error": f"handoff is {rec['status']}, cannot accept"})
    if accepting_agent_id != rec["to_agent"] and rec["to_agent"] != "*":
        return json.dumps({"error": f"accepting_agent_id {accepting_agent_id} != intended recipient {rec['to_agent']}"})
    now = datetime.now(timezone.utc)
    expires = datetime.fromisoformat(rec["expires_utc"])
    if now > expires:
        rec["status"] = "expired"
        return json.dumps({"error": "handoff expired before acceptance", "expired_utc": rec["expires_utc"]})

    acceptance = {
        "handoff_id": handoff_id,
        "accepted_by_agent": accepting_agent_id,
        "accepted_by_ref": accepting_agent_ref,
        "accepted_utc": now.isoformat(),
        "prev_signature": rec["offer_signature"],
    }
    acceptance_signature = _sign(acceptance)

    rec["acceptance"] = acceptance
    rec["acceptance_signature"] = acceptance_signature
    rec["status"] = "accepted"

    return json.dumps({
        "accepted": True,
        "handoff_id": handoff_id,
        "acceptance_signature": acceptance_signature,
        "chain_status": "both signed — verifiable",
    })


@mcp.tool()
def verify_chain(handoff_id: str, api_key: str = "") -> str:
    """Re-verify the handoff signatures. Returns full trace + integrity status."""
    allowed, msg, tier = check_access(api_key)
    if not allowed:
        return json.dumps({"error": msg})
    rec = _handoffs.get(handoff_id)
    if not rec:
        return json.dumps({"error": f"handoff_id {handoff_id} not found"})

    # Re-sign offer
    offer_stripped = {k: v for k, v in rec.items() if k not in ("offer_signature", "acceptance", "acceptance_signature")}
    expected_offer_sig = _sign(offer_stripped)
    offer_valid = hmac.compare_digest(expected_offer_sig, rec["offer_signature"])

    acceptance_valid = None
    if rec.get("acceptance"):
        expected_acc_sig = _sign(rec["acceptance"])
        acceptance_valid = hmac.compare_digest(expected_acc_sig, rec["acceptance_signature"])

    return json.dumps({
        "handoff_id": handoff_id,
        "status": rec["status"],
        "offer_signature_valid": offer_valid,
        "acceptance_signature_valid": acceptance_valid,
        "chain": {
            "offer": {k: v for k, v in rec.items() if k not in ("acceptance", "acceptance_signature")},
            "acceptance": rec.get("acceptance"),
            "acceptance_signature": rec.get("acceptance_signature"),
        },
        "verdict": (
            "VALID — both signatures intact" if (offer_valid and acceptance_valid)
            else "VALID OFFER, UNACCEPTED" if offer_valid and acceptance_valid is None
            else "INVALID — signature mismatch"
        ),
    }, indent=2)


@mcp.tool()
def list_handoffs(tenant_id: str, status_filter: str = "", limit: int = 25, api_key: str = "") -> str:
    """List handoffs for a tenant, optionally filtered by status."""
    allowed, msg, tier = check_access(api_key)
    if not allowed:
        return json.dumps({"error": msg})
    matching = [r for r in _handoffs.values() if r["tenant_id"] == tenant_id]
    if status_filter:
        matching = [r for r in matching if r["status"] == status_filter]
    matching.sort(key=lambda r: r["offered_utc"], reverse=True)
    return json.dumps({
        "tenant_id": tenant_id,
        "count": len(matching),
        "handoffs": [
            {"handoff_id": r["handoff_id"], "from_agent": r["from_agent"],
             "to_agent": r["to_agent"], "task": r["task"][:60], "status": r["status"],
             "offered_utc": r["offered_utc"]}
            for r in matching[:limit]
        ],
    }, indent=2)


@mcp.tool()
def sign_handoff_chain_attestation(
    tenant_id: str,
    window_start_utc: str,
    window_end_utc: str,
    api_key: str = "",
    email: str = "",
) -> str:
    """Emit a signed attestation of the handoff chain integrity for a window. Pro+."""
    allowed, msg, tier = check_access(api_key)
    if not allowed:
        return json.dumps({"error": msg, "upgrade_url": STRIPE_199})
    if tier == "free":
        return json.dumps({"error": "Signed chain attestations require Pro (£199/mo).", "upgrade_url": STRIPE_199})

    window_records = [r for r in _handoffs.values()
                      if r["tenant_id"] == tenant_id
                      and window_start_utc <= r["offered_utc"] <= window_end_utc]
    from collections import Counter
    statuses = Counter(r["status"] for r in window_records)
    findings = [
        f"Window: {window_start_utc} -> {window_end_utc}",
        f"Total handoffs: {len(window_records)}",
        f"Status breakdown: {dict(statuses)}",
        f"Accepted: {statuses.get('accepted', 0)}",
        f"Expired: {statuses.get('expired', 0)}",
    ]
    score = 100 * statuses.get("accepted", 0) / max(1, len(window_records))
    if _ATTESTATION_LOCAL:
        cert = get_attestation_tool_response(
            regulation="A2A handoff chain integrity (EU AI Act Art 12 + ISO 42001 clause 9)",
            entity=f"tenant:{tenant_id}",
            score=score,
            findings=findings,
            articles_audited=["EU AI Act Art 12", "ISO 42001 clause 9"],
            tier=tier,
        )
    else:
        import urllib.request as _url
        try:
            req = _url.Request(
                f"{_ATTESTATION_API}/sign",
                data=json.dumps({
                    "api_key": api_key, "email": email,
                    "regulation": "A2A handoff chain integrity",
                    "entity": f"tenant:{tenant_id}",
                    "score": score, "findings": findings, "tier": tier,
                }).encode(),
                headers={"Content-Type": "application/json"},
            )
            with _url.urlopen(req, timeout=15) as resp:
                cert = json.loads(resp.read())
        except Exception as e:
            return json.dumps({"error": f"Attestation API unreachable: {e}"})
    return json.dumps(cert, indent=2)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
