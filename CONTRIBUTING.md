# Contributing Guidelines & Engineering Standards

Welcome to **castel-credcam**! This project focuses on: Photo credential capture application for school lab environments.

---

## 🏛️ Code of Conduct & Mutual Respect

All contributors, reviewers, and maintainers are required to follow our [Code of Conduct](CODE_OF_CONDUCT.md).
We expect all discussions in issues and pull requests to remain professional, constructive, and technically grounded.
**Insults, demanding entitlement, toxic behavior, or harassment will result in immediate thread locking and account blocking.**

---

## 📋 Issue-First Workflow (Mandatory)

Before opening a Pull Request:
1. **Search existing issues** to avoid duplicate proposals.
2. **Open an Issue first** describing the bug with logs and environment details, or detailing the proposed feature before writing code.
3. **Wait for maintainer approval** before undertaking large refactors or adding dependencies. Unsolicited massive PRs rewriting core architecture will be closed without review.

---

## 🛠️ Stack & Quality Standards (Python / OpenCV / PyQt)

* **Quality Gates**:
  - Verification command: `pytest` must pass cleanly.
  - Linting command: `ruff check .` must produce zero errors and adhere to existing style.
* **Privacy & Security**: Never commit credentials, private API keys, internal network IPs, or institutional data.
* **Clean Commits**: Use descriptive imperative commit messages following Conventional Commits (`feat: ...`, `fix: ...`, `docs: ...`).

---

## 🤖 AI-Assisted and Agent Contributions

We enforce a strict **Zero-Slop Policy**:
* If an AI was used, disclose it in the PR description.
* The human contributor assumes **100% engineering responsibility** for every line of code submitted.
* Fabricated APIs, hallucinated dependencies, non-compiling boilerplate, or unchecked AI output will be closed immediately as spam.
* Detailed requirements for automated tools and AI agents are documented in [AGENTS.md](AGENTS.md).
