# Agent Handoff Certified MCP

[![PyPI](https://img.shields.io/pypi/v/agent-handoff-certified-mcp)](https://pypi.org/project/agent-handoff-certified-mcp/) [![Python](https://img.shields.io/pypi/pyversions/agent-handoff-certified-mcp)](https://pypi.org/project/agent-handoff-certified-mcp/)


**Verifiable agent-to-agent handoffs with cryptographic chain**

When agent A delegates to agent B (cross-process, cross-network, cross-org), both ends sign. verify_chain reconstructs + validates the full trace. Non-repudiation for multi-agent workflows.

By [MEOK AI Labs](https://meok.ai).

## Install

```bash
pip install agent-handoff-certified-mcp
```

## Tools

- `initiate_handoff`
- `accept_handoff`
- `verify_chain`
- `list_handoffs`
- `sign_handoff_chain_attestation`

## Claude Desktop

```json
{
  "mcpServers": {
    "agenthandoffcertified": { "command": "agent-handoff-certified-mcp" }
  }
}
```

## Tiers

- **Free** — generous daily limit (100-1,000 depending on operation)
- **Pro £199/mo** — unlimited + signed HMAC attestations with public verify URLs — [subscribe](https://buy.stripe.com/14A4gB3K4eUWgYR56o8k836)
- **Enterprise £1,499/mo** — multi-tenant + custom predicate DSL + SIEM webhook push — [subscribe](https://buy.stripe.com/4gM9AV80kaEG0ZT42k8k837)

## Why this exists

The EU AI Act (Aug 2026), DORA (live), ISO 42001, and OWASP LLM01 Top-10 all demand runtime controls for agent systems — not just deployment-time audits. This MCP is that runtime control layer, emitting cryptographically signed evidence your auditor accepts.

## Related MEOK A2A MCPs

- [`agent-policy-enforcement-mcp`](https://pypi.org/project/agent-policy-enforcement-mcp/) — per-pair IAM
- [`agent-handoff-certified-mcp`](https://pypi.org/project/agent-handoff-certified-mcp/) — signed delegation chain
- [`agent-prompt-injection-firewall-mcp`](https://pypi.org/project/agent-prompt-injection-firewall-mcp/) — prompt injection WAF
- [`agent-rate-limiter-mcp`](https://pypi.org/project/agent-rate-limiter-mcp/) — fleet-wide quota
- [`agent-audit-logger-mcp`](https://pypi.org/project/agent-audit-logger-mcp/) — hash-chained signed log
- [`a2a-governance-bridge-mcp`](https://pypi.org/project/a2a-governance-bridge-mcp/) — map A2A to compliance frameworks
- [`meok-attestation-verify`](https://pypi.org/project/meok-attestation-verify/) — independent cert verifier

## License

MIT — MEOK AI Labs, 2026.

<!-- mcp-name: io.github.CSOAI-ORG/agent-handoff-certified-mcp -->
