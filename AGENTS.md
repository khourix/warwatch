# AGENTS.md: entry point for AI agents

This repo has no full agent kit yet. Read `README.md` first.

## Engineering skills (pstack)

Hermes and Claude Code load poteto's pstack skills (used live and unmodified from github.com/cursor/plugins) on every machine. This file wins over them.

- Load `pstack-harness` before any pstack skill. It maps tools and models, and its rules (no merging, delete checks, plain-language replies) win over pstack.
- Rigorous work (bug fix, feature, perf, refactor): start with `/poteto-mode`. It picks a playbook.
- A report or a vague ask: `/in-your-own-words` first. The agent restates the problem and the owner confirms.
- Explain a choice to the owner: `/teach`. How code works: `/how`. Why it is this way: `/why`.
- Resume earlier work: `/recall`. Design across modules: `/architect`. Parallel checks: `/swarm`.
- Docs and READMEs: `/technical-writing`, then `/unslop`.

**Verification skill: `verify-warwatch`** at `.agents/skills/verify-warwatch/` (symlink `.claude/skills/verify-warwatch`). Hermes loads repo skills only after `hermes skills trust` in the repo. It proves: the site builds, pages render (screenshot as proof), links resolve, and the data is fresh.

Before you open a PR, run `.agents/skills/verify-warwatch/verify.sh full` and paste the result.
