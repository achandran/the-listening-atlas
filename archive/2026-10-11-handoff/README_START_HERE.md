# The Listening Atlas — coding-agent handoff

1. Give the agent `AGENT_PROMPT.md` as the main instruction.
2. Attach or extract this entire package so the agent can inspect `source/` and `editorial/`.
3. Ask it to show an import/reconciliation plan before it modifies repertoire data.

## Snapshot versus editorial intent

The latest provided master contains **669 rows**. It reflects the approved two-Trifonov-minuet opening and the Hewitt Inventions / Ólafsson Aria variata substitutions. It does **not** fully reflect the 19-track Breath plan. The agent must distinguish source-data migration from later editorial reconciliation.

The original HTML is a reference implementation, not the desired long-term canonical data format. The XLSX and CSV are reference exports; new canonical source should be human-editable and diff-friendly.

## Scope

The handoff contains editorial material and source exports, not a ready-to-deploy application. Apple Music access requires separate user authentication; do not automate live edits without approval.
