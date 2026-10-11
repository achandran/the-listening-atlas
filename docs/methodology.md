# Methodology

## The Atlas's method

> Listen to what the music is doing; let expressive understanding arise from audible musical relationships.

This is the only principle that holds across the whole Atlas. It is deliberately a method, not an aesthetic:
it asks the listener to attend to bass, harmony, voice-leading, rhythm, phrase, counterpoint, proportion,
form and transformation, and to let expression be understood *through* those relationships rather than
imposed on them.

Recordings are listening lenses, not authorities. They are chosen for how clearly they reveal musical causes;
editorial preferences among performers (for the Bach volume: Perahia principal, Hewitt secondary, Ólafsson
tertiary — with Trifonov in Ground) are preferences, not exclusions.

## Volumes have their own principles

Each volume (a *collection* in the data) defines:

- its own principle (`volume_principle` in `collection.yaml`),
- its own stages, each with a principle, listening question, direction, an "at the piano" exercise and a
  recording itinerary (`stages.yaml`),
- its own fallback listening prompts (`fallback_prompts`), and its own work-level and close-listening notes.

One rule holds for every volume: **within a volume's playlist, each recording appears at most once** —
no duplicate entries. Different performances of the same music may both appear.

Nothing about stages is hard-coded in the application. The number of stages, their names, and their questions
are all data.

### Bach: Cantabile & Harmony

The Bach volume's principle is *cantabile* — making the musical line sing — as the way into Bach's musical
relationships, with eleven cumulative hearing stages from Ground to Essence. This is specific to Bach. It must
not be copied into other volumes as if it were the Atlas's universal principle.

## Adding a volume

1. Write the curriculum first — editors only. Don't derive one composer's stages from another's.
2. Add works to `data/works/<composer>.yaml` with the composer's own catalogue (K., D., Op., Hob., …). Work
   IDs are lowercase slugs, e.g. `k-331`, `op-110`.
3. Add recordings to `data/recordings.yaml`.
4. Create `data/collections/<id>/` with `collection.yaml`, `stages.yaml`, one selections file per stage,
   `notes/`, `issues.yaml` and `retired.yaml` (copy the structure, not the content, of the Bach volume).
5. List the collection in `data/atlas.yaml`.
6. Run `uv run atlas validate && uv run atlas build`.

The website, exports and validator need no code changes for a new volume.

## The website is a read view

The site presents each playlist with its listening questions, notes and Apple Music links, plus search.
Readers can't record anything on it: there are no checklists, note fields or accounts, and it stores
nothing in the browser. Listening notes belong in the reader's own notebook. Adding interactive features
would be a deliberate, separate decision.
