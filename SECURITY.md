# Security Policy

## Purpose

This document defines the security posture and vulnerability disclosure process for COS-Monitor (`company-os-monitor`).

## Scope

Applies to the `company-os-monitor` implementation repository, including all services, agents, infrastructure configuration, and the web frontend.

## Vulnerability Reporting

### How to Report

Security vulnerabilities should be reported through the [GitHub Security Advisory](https://github.com/danielcba/company-os-monitor/security/advisories) mechanism. This is the primary and currently available channel for vulnerability disclosure.

### What to Include in a Report

- **Description**: Clear explanation of the vulnerability.
- **Affected component**: Repository, file, or module where the issue exists.
- **Steps to reproduce**: Enough detail to allow triage.
- **Impact**: What an attacker could achieve.
- **Suggested fix** (optional): Proposed remediation path.

### What NOT to Send Publicly

- Do not report security vulnerabilities in public issues, pull requests, or discussion threads before a fix is available.
- Do not share full exploit code publicly before remediation.
- Do not expose secrets, tokens, or credentials in any public channel.

### What NOT to Send in Reports

- Do not include production secrets, private keys, or credentials in vulnerability reports unless explicitly requested through a secure channel after triage.

## Triage Process

1. **Acknowledgment**: Report is acknowledged within 5 business days.
2. **Assessment**: Severity is evaluated against the cognitive architecture invariants (R1–R7).
3. **Remediation**: Fix is developed following the framework remediation protocol.
4. **Disclosure**: Coordinated disclosure after a fix is deployed.

## Acknowledgment and Tracking

Reporters are acknowledged upon triage completion. Fixes are tracked against the monitor's remediation plan. Critical and High findings receive priority handling.

## Critical Vulnerabilities

Critical vulnerabilities affecting the cognitive architecture invariants, JWT validation, multi-tenancy isolation, authorization boundaries, or agent authentication are treated as **P0**. They follow the fail-closed principle: the system must not be downgraded to an insecure state while awaiting remediation.

## Agent Security

Agents (WinRM, vSphere, network) must use authenticated channels. TLS is required but not sufficient for agent authentication. Machine JWTs with kid-based rotation (ADR-0005 §1) are the canonical mechanism for agent-to-gateway authentication. Agent credentials must be stored in secure vaults, never in source code or configuration files.

## Channel

The currently available channel for security disclosure is:

- **GitHub Security Advisories**: [https://github.com/danielcba/company-os-monitor/security/advisories](https://github.com/danielcba/company-os-monitor/security/advisories)

This repository does not currently maintain a dedicated security mailing list. The GitHub Security Advisory mechanism is the canonical channel for vulnerability reporting.

## Relationship to Framework

All security controls must comply with the **R1–R7 Design Rules** defined in `docs/cognitive-architecture/cognitive-architecture.md`. The Monitor implements the canonical cognitive flow and all external capabilities are labeled as non-canonical per ADR-0002.
