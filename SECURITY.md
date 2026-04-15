# Security Policy

> **CoReason, Inc. — Vulnerability Disclosure Program (VDP)**

## Supported Versions

Security updates are provided exclusively for the following:

| Version | Supported |
|---------|-----------|
| `main` branch (HEAD) | ✅ Active |
| Latest minor release (`>= 0.3.x`) | ✅ Active |
| Previous minor releases (`< 0.3.0`) | ❌ End-of-Life |
| Pre-release / `develop` branch | ❌ Best-effort only |

> [!IMPORTANT]
> Only the `main` branch and the latest published minor release receive security patches. Users on older versions must upgrade to receive fixes.

---

## Reporting a Vulnerability

> [!CAUTION]
> **All security issues MUST be reported privately. Do NOT open a public GitHub Issue.**

If you discover a security vulnerability in `coreason-ecosystem`, please report it responsibly:

1. **Email:** Send a detailed report to **[security@coreason.ai](mailto:security@coreason.ai)**
2. **Subject Line:** `[VULN] coreason-ecosystem — <Brief Description>`
3. **Include:**
   - A clear description of the vulnerability
   - Steps to reproduce (PoC if applicable)
   - Affected version(s) and component(s)
   - Your suggested severity assessment (Critical / High / Medium / Low)
   - Your contact information for follow-up

### PGP Encryption (Optional)

For highly sensitive disclosures, you may encrypt your report using our PGP key available at:
```
https://coreason.ai/.well-known/security.txt
```

---

## Response SLA

We are committed to the following response timeline:

| Milestone | Timeline |
|-----------|----------|
| **Acknowledgement** | Within **48 hours** of receipt |
| **Initial Triage** | Within **3 business days** |
| **Remediation Timeline** | Communicated within **5 business days** |
| **Patch Release** | Per severity — Critical: ≤7 days, High: ≤14 days, Medium/Low: next scheduled release |

We will keep reporters informed throughout the remediation process and will credit reporters (with consent) in the security advisory.

---

## Scope

### In-Scope

The following components are covered by this security policy:

- **Supply Chain Security** — CI/CD pipeline integrity, dependency resolution, WASM registry signing
- **CLI Router** — Typer command injection, argument parsing vulnerabilities
- **Fleet Orchestration** — Pulumi actuator, mesh injector, pricing oracle
- **Telemetry Pipeline** — OTLP worker, SSE aggregation, data exfiltration vectors
- **Infrastructure Templates** — Docker Compose manifests, cloud provisioning scripts
- **Cryptographic Operations** — SHA-256 hashing, JWT validation, attestation receipts

### Out-of-Scope

The following are **not** considered valid security findings:

- Version fingerprinting via PyPI metadata or `--version` CLI output
- Descriptive error messages that do not leak sensitive data
- Denial-of-service via intentionally malformed CLI input (expected behavior)
- Issues in upstream dependencies (`coreason-manifest`, `coreason-runtime`) — report those to their respective repositories
- Social engineering attacks against CoReason personnel
- Issues requiring physical access to the deployment infrastructure

---

## Supply Chain Hardening

This repository implements the following security controls:

- **SLSA Level 3** build provenance via GitHub Actions
- **Sigstore** artifact signing for all published packages
- **SBOM** (SPDX) generation for every release
- **CodeQL** static application security testing on every PR
- **OpenSSF Scorecard** continuous security posture assessment
- **Step Security Harden Runner** with egress filtering on all CI jobs
- **Reproducible Builds** with SHA-256 determinism verification
- **Bandit** SAST scanning with zero-tolerance policy

---

## Disclosure Policy

CoReason follows a **coordinated disclosure** model:

1. Reporter submits vulnerability privately via email
2. CoReason acknowledges and triages within the SLA
3. A fix is developed and tested in a private branch
4. A security advisory is published via [GitHub Security Advisories](https://github.com/CoReason-AI/coreason-ecosystem/security/advisories)
5. The patched release is published to PyPI
6. The reporter is credited (with their consent)

We request that reporters allow a **90-day disclosure window** before publishing details publicly.

---

## Contact

- **Security Reports:** [security@coreason.ai](mailto:security@coreason.ai)
- **General Inquiries:** [info@coreason.ai](mailto:info@coreason.ai)
- **Security Advisories:** [GitHub Security Tab](https://github.com/CoReason-AI/coreason-ecosystem/security/advisories)

---

*Copyright (c) 2026 CoReason, Inc. Licensed under the Prosperity Public License 3.0.*
