# Project Seek V3: ELT Blueprint (Late-Binding Lenses)

## 1. Core Architectural Shift: ELT (Extract, Load, Transform)
Project Seek V3 transitions from an ETL (Extract, Transform, Load) model to an **ELT (Extract, Load, Transform)** model. This is defined by **Late-Binding Lenses**.

### Ingestion Layer (Extract & Load)
The Ingestion layer (driven by Forager or Manual entry) is strictly objective. 
- It strips out fluff and extracts dense, objective pointers from the source content.
- The output of this layer is a **Neutral Brick**.
- **Crucial Rule:** NO LENSES are applied at ingestion. We only store the raw, dense facts, mechanisms, and claims.

### Librarian / Query Layer (Transform / Late-Binding)
Lenses are now applied dynamically, on-demand, at query time by the Librarian.
- Lenses available: **Architect**, **Growth**, **First Principles**, **Red Team**, **Validator**.
- When the user queries the system, the Librarian retrieves the relevant Neutral Bricks and applies the appropriate lens(es) based on the current context to generate insights.

## 2. Dual-Layer Context
All Librarian / Query operations are governed by a **Dual-Layer Context**:
1. **Mission Directive:** The overarching, long-term goal or North Star of the user/system.
2. **Focus State:** The immediate, current tactical problem or sprint focus.

This dual context ensures that the late-bound lenses shape the Neutral Bricks into advice that is both strategically aligned and tactically immediately useful.

## 3. Database Schema Review (`src/db/models.py`)

### Assessment of `strategy_library` Table
The current `strategy_library` schema is **not generic enough** to serve as our 'Neutral Brick' schema and **requires a database migration**.

**Reasons for Migration:**
1. **`lens_used` Column:** This column violates the ELT/Late-Binding architecture. If we apply lenses at query time, there is no `lens_used` at the ingestion layer.
2. **Prescriptive Columns:** Columns like `strategy_name`, `failure_modes`, and `implementation_challenge` are highly interpretative. They represent the *output* of a lens (like the Architect or Red Team lens), not an objective Neutral Brick.
3. **Table Nomenclature:** `strategy_library` implies the data is already a "strategy". In V3, the stored data is a "Neutral Brick", which only becomes a strategy when a lens is applied.

**Migration Recommendations:**
- Rename the `strategy_library` table to `neutral_bricks` (or similar).
- Drop the `lens_used` column.
- Refactor columns to capture purely objective extractions. 
  - *Keep/Adapt:* `core_concept` (rename to `mechanism` or `core_claim`), `why_it_works` (can remain if kept strictly objective).
  - *Remove:* `strategy_name`, `failure_modes`, `implementation_challenge`.
  - *Add:* `source_quote` or `objective_context` to capture the dense pointer without interpretation.
