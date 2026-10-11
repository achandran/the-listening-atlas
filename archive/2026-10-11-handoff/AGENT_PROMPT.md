# Coding agent brief — The Listening Atlas

Build a production-quality, Git-friendly, open-source repository named `the-listening-atlas` from the files in this handoff package. This is a curated, pedagogical classical-music listening atlas that will expand to other composers. The Bach volume is **Bach: Cantabile & Harmony**. Do NOT impose cantabile as a universal principle on future composers. The cross-composer method is: listen to what the music is doing; let expressive understanding arise from audible musical relationships.

## Inputs and source-of-truth precautions

Inspect every file under `source/` and `editorial/` before transforming it. The latest machine-readable *export snapshot* is `source/Bach_Cantabile_Master_Ground_Revised.csv` (669 rows), with a corresponding playlist-transfer CSV, interactive HTML, and XLSX. The student guide and replacement audit provide additional editorial context. Preserve the original inputs under `archive/` or equivalent, with checksums and provenance. Do not silently replace source content with assumptions.

**Known editorial state and unresolved issues**

- Stage 1 Ground: the approved first two tracks are Daniil Trifonov, Minuet G major BWV Anh.114 (Christian Petzold), Apple song ID `1577781357`, then Minuet A minor BWV Anh.120 (composer uncertain), Apple song ID `1577780575`; both from album `1577776877`. They replace the previous BWV511 opening, not add to it. The latest snapshot has 20 Ground tracks. A prior discussion floated BWV939 as first Hewitt prelude, but the latest CSV actually has BWV924 as its third track. **Do not silently reorder the Hewitt preludes**; flag this discrepancy for editorial review.
- Stage 2 Breath: the user approved a 19-track sequence that is NOT fully integrated into the latest 669-row snapshot. See `editorial/BREATH_19_APPROVED.md`. Build an editorial reconciliation report and an optional proposed patch, but do not silently present the snapshot as fully synchronized or fabricate recording IDs.
- Stage 4 Line: replace Schiff's Inventions and Sinfonias with Angela Hewitt's 1994 Hyperion cycle; some exact Apple song IDs and durations remain unverified. Retain the replacement audit.
- Stage 7 Span: use Víkingur Ólafsson's 2018 DG BWV989 Aria variata, including its concluding Aria da capo. Check sequence/IDs before synchronization.
- Stage 8 Order: Angela Hewitt's *later* 2008-recorded/2009-released Hyperion Well-Tempered Clavier, BOTH books (96 tracks), not her earlier cycle.
- Perahia principal, Hewitt secondary, Ólafsson tertiary is an editorial preference, not a rigid exclusion; Trifonov remains in Ground.
- No changes should be made to a live Apple Music playlist without explicit user approval and a dry-run review.

## Deliverables

1. Clean documented repo with `README.md`, `CONTRIBUTING.md`, `LICENSE` placeholder if license isn't chosen, `docs/methodology.md`, `docs/data-model.md`, `docs/apple-music-sync.md`, `docs/editorial-status.md`, and a provenance manifest.
2. A **canonical, human-editable, diff-friendly data model** (YAML or JSON files; prefer YAML with stable IDs and a schema). Separate musical works, recordings, playlist selections, stages, and listening notes appropriately. Preserve **all 669 source entries, original order, raw titles, credits, URLs, status, and editorial notes** in the initial migration. Avoid generating thousands of noisy changed lines when moving one selection; stable selection IDs are essential. Preserve source columns losslessly in a raw snapshot or sidecar.
3. A composer-independent collection model, with Bach's 11 stages as data, not hardcoded into the application. Future Mozart/Beethoven/etc. collections can have different principles and stage structures. Do not invent their curricula.
4. A validator with clear errors for duplicate selection IDs, missing work/recording references, missing/invalid stage numbers, mismatched order, unresolved song IDs, broken URLs, and suspicious duplicate works. Distinguish deliberate reuse from accidental duplication. Do not assume a title alone identifies a recording.
5. Deterministic command-line tools, e.g. `atlas validate`, `atlas export --format csv`, `atlas build`, `atlas audit`, with documented install/run commands. Provide a lockfile and pinned dependencies. Include tests and CI (lint, type checks if applicable, schema validation, snapshot export tests).
6. A modern, accessible, responsive static listening website generated from the canonical data. Preserve the existing HTML guide's substantive listening prompts and features: stage navigation, search, work details, Apple Music links, completion checkboxes, journaling and local progress export. Keep user notes local unless explicitly asked to implement an account service. Make keyboard navigation and mobile usage good. Prefer a simple static deployment (e.g. GitHub Pages) and avoid unnecessary backend infrastructure.
7. Export full playlist and stage-specific playlists to CSV in a documented importer-compatible schema. For each item retain exact performance metadata and Apple song URL/ID if known; report missing/unverified matches. Document how to use Soundiiz/TuneMyMusic with manual review. Do not imply Apple Music directly imports arbitrary CSV files.
8. OPTIONAL phase two: design (but don't activate by default) an Apple Music MusicKit/API synchronization command with credentials only from environment variables, dry-run plan, exact song-ID matching, clear handling of reordered tracks, and explicit confirmation for destructive operations. No secrets committed. If API permissions or reorder operations are unavailable, report that limitation rather than claiming sync works.
9. A migration report comparing canonical track count/order against the supplied 669-row snapshot; a separate **editorial discrepancy report** for approved-but-not-yet-merged changes (especially Breath). Tests must assert all 669 entries survive migration without loss, and the first two Ground song IDs remain correct.

## Data model suggestion

Each playlist selection should have a stable `selection_id`, `stage_id`, `order`, `work_id`, `recording_id`, `movement`, `listening_focus`, `apple_music_song_id`, `apple_music_url`, `verification_status`, and provenance. Works and recordings can be reused across playlists without duplicating their metadata. A stage has its own principle and guiding question. Recordings must identify pianist/ensemble/conductor, album and recording version (e.g., Hewitt later WTC). For unverified data, use explicit `null` or status `needs_verification`, never fabricated URLs, ISRCs, durations or IDs.

## Process and acceptance criteria

- First inspect inputs, publish a concise migration plan and discrepancies, then implement.
- Keep original source files untouched and avoid changing musical/editorial decisions without flagging them.
- Provide exact commands to run locally, build the site, test, export, and publish to GitHub Pages.
- Demonstrate deterministic exports and tests; include an example of a clean Git diff when one selection changes.
- Show the user the pending editorial issues before resolving them.
- Do not create a GitHub repo, push to GitHub, access Apple Music credentials, or modify a live playlist without explicit permission.

## Existing public Apple Music playlist

https://music.apple.com/us/playlist/bach/pl.u-kv9lRpvs7v0a9Yb

Treat this as a public reference, not as proof that the local export and live playlist are identical.
