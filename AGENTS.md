# Engineering Standards for AI Agents & Automated Contributors (AGENTS.md)

This document establishes the binding engineering guidelines for any **Autonomous Agent**, **LLM-assisted developer**, or **Automated CI/CD Workflow** submitting issues, pull requests, or code reviews to the **castel-credcam** repository.

---

## 🧭 Core Principles

1. **Human Ownership & Accountability**:
   Automated agents and AI models do not hold legal or technical accountability. The human author whose credentials push the code or open the PR assumes **full responsibility** for the correctness, performance, security, and maintenance of the changes.

2. **Transparent Disclosure**:
   In accordance with open source best practices, contributors must explicitly disclose the involvement of AI agents or LLMs in the PR description:
   ```markdown
   ### 🤖 AI Assistance Disclosure
   - Tools used: [e.g., Claude Code, Cursor, Copilot, Custom Agent]
   - Human verification: Fully reviewed, locally verified, and all checks passed.
   ```

3. **Zero AI Slop & Anti-Hallucination Policy**:
   PRs containing any of the following will be **immediately closed without review, marked as spam, and may result in a contributor block**:
   * Hallucinated packages, fake SDK/framework methods, or non-existent standard library functions.
   * "Plumbing without water": empty boilerplate files, dummy implementations, or unneeded scaffolding.
   * Unrequested refactoring of working code without functional or performance justification.
   * Broken syntax, failing builds, or unhandled runtime errors.
   * Circular, repetitive LLM apologies in issue or review threads.

---

## 🧪 Verification & Evidence Requirement (Python / OpenCV / PyQt)

Every PR submitted to castel-credcam with AI assistance **must include verifiable evidence of local execution**:

* **Build / Verification**:
  - `pytest` must pass with zero errors.
* **Linting & Formatting**:
  - `ruff check .` must pass cleanly without warnings.
* **Deterministic Reproduction**:
  - Bug fixes must include minimal reproduction steps or a test asserting the fix.

---

## 🚫 Forbidden AI Behaviors

* **Unsolicited Mass PRs**: Automated bots opening batch PRs without maintainer pre-approval.
* **Credential or Token Leakage**: Never commit simulated or real API tokens, session cookies, or private keys.
* **Review Spam**: Posting automated LLM code reviews on PRs unless specifically invited by the repository maintainers.

---

## 🏛️ Code of Conduct Compliance

All interactions generated or facilitated by AI tools must strictly adhere to our [Code of Conduct](CODE_OF_CONDUCT.md). Hostile, entitled, or automated spam responses will lead to immediate repository-level and organization-level blocking.
