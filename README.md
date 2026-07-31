# Jobbot

A local-first job discovery and application workspace. Jobbot combines a
structured candidate profile, private CV evidence, persisted search controls,
0-100 Gemini match scoring, application tracking, and tailored cover letters.

## Architecture

```text
LinkedIn guest search ----+
Greenhouse company boards +--> source adapters --> data/job_*.json
Lever company boards -----+                             |
               v
React dashboard <--> FastAPI <--> run manager --> idempotent importer --> SQLite
            |
            +--> analyzer.py --> Gemini scoring
            +--> CV extraction + cover letters
```

- **Existing pipeline**
  - `scraper.py` remains the only LinkedIn scraping implementation.
  - Greenhouse and Lever use their public company job-board APIs through
    adapters under `backend/sources/`.
  - `analyzer.py` remains the only Gemini evaluation implementation.
  - `main.py` remains available as the command-line pipeline.
- **Backend** (`backend/`)
  - FastAPI endpoints for jobs, structured profiles, CVs, search controls,
    runs, history, applications, and cover letters.
  - SQLite persistence in `jobbot.db` (ignored by Git).
  - Idempotent startup import of all `data/job_*.json` files.
  - URL-first job deduplication with exact-content cross-source fallback.
  - A guarded background run manager prevents concurrent duplicate runs.
- **Frontend** (`frontend/`)
  - React, Vite, and TypeScript.
  - One-time candidate setup followed by a search-first home workspace, ranked
    match results, secondary results dashboard, score breakdowns, search
    history, Kanban-style applications board, structured profile editor, CV
    upload, and editable cover letters.
  - The Gemini key is never included in the frontend bundle.

## Prerequisites

- Python 3.12+
- Node.js 20+ and npm
- A Gemini API key

## Initial setup (Windows PowerShell)

From the repository root:

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
playwright install chromium
Copy-Item .env.example .env
```

Edit `.env` and set:

```dotenv
GEMINI_API_KEY=your_real_gemini_api_key
```

Install the frontend dependencies:

```powershell
Set-Location frontend
npm install
Set-Location ..
```

The `.env`, `.venv`, `data/` (including uploaded CVs), `jobbot.db`, and frontend
build/dependency folders are ignored by Git.

## Structured workflow

1. Open **Start a Search**. The first visit guides you through the essential
  candidate setup before showing roles and filters.
2. Upload a PDF or DOCX CV. The original file and locally extracted raw text are
  stored under `data/cv/` and never returned by the API.
3. Select **Extract Profile from CV** to let Gemini populate supported structured
  fields. Review the essential profile in step one; the full profile editor
  remains available for education, experience, languages, and cover letters.
4. On later visits, **Start a Search** opens directly to the saved candidate
  overview and search controls. Use **Edit core details** or **Open full
  profile** only when the candidate information needs updating.
5. Set keywords, locations, work models, threshold, top-result
  count, seniority/language/location exclusions, and source adapters.
  Search keywords are the single source for target roles and are used for both
  source discovery and Gemini career-alignment scoring.
6. Select **Start Job Search** directly from the search controls. There is no
  separate review step and there are no separate discovery, analyzer, or
  full-pipeline actions in the web UI. Every search discovers normalized jobs,
  scores each from 0-100,
  applies deterministic hard filters, and shows only qualifying top matches.
7. Open a match to inspect strengths, concerns, missing requirements, score
  breakdown, resume keywords, and application strategy.
8. Generate, edit, copy, or regenerate a grounded cover letter.

**Job Matches** is the focused shortlist and uses the currently saved score
threshold and top-result count. Reducing the count does not delete older jobs or
analyses. Change a match's application status directly in the list to add or
move it on the application board without opening the detail drawer. Open
**Search History** to revisit the exact criteria and results from any previous
search. Historical results default to qualifying matches, can be filtered to
all analyzed jobs, non-matches, or errors, and open the same job detail and
application-tracking drawer used elsewhere.

Finished history can be cleaned up without losing application work. Removing a
completed search hides that history entry while preserving its analyses, jobs,
applications, and cover letters. Deleting a failed or empty search permanently
removes its run and analysis records; shared jobs, application tracking, and
cover letters remain.

After launch, the app opens the secondary **Results Dashboard** to show search
progress, top matches, and application metrics. Search configuration remains the
main home-page experience.

### Search sources

- **LinkedIn** performs broad keyword and location discovery through public
  guest endpoints.
- **Greenhouse** and **Lever** scan public feeds for selected companies. These
  ATS platforms do not offer a global search API, so select the source and add
  one or more company board targets under **Company job boards**.
- A target can be a board token/site name, a full board URL, or
  `Company name | token-or-URL`. Supplying the company name gives cleaner job
  cards when the ATS response does not identify its owner.

Examples are `Acme | acme`, `https://boards.greenhouse.io/acme`, and
`https://jobs.lever.co/acme`. Each adapter filters the company feed using the
saved role and location controls. One failing company board is recorded as a
source warning while the other selected sources continue.

Workday, generic career pages, manual URLs, and broad third-party job-board APIs
remain explicit future adapters; the UI does not claim they are connected.

### Match score interpretation

- **90-100:** Excellent match
- **75-89:** Strong match
- **60-74:** Possible match
- **Below 60:** Hidden by default

The score covers title, skills, experience, location, work model, education,
certifications, language requirements, career goals, cover-letter relevance,
and critical requirements. The saved minimum threshold and hard exclusions make
the final `qualifies` decision deterministic after Gemini returns its evidence.

## Run locally for development

Use two PowerShell terminals.

### Terminal 1 — FastAPI

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
```

API documentation is available at <http://127.0.0.1:8000/docs>.

### Terminal 2 — React/Vite

```powershell
Set-Location frontend
npm run dev
```

Open <http://localhost:5173>.

## Run as one local server

Build the frontend, then let FastAPI serve it:

```powershell
Set-Location frontend
npm run build
Set-Location ..
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>. Direct URLs such as `/jobs`, `/profile`, and
`/applications` are supported by the SPA fallback.

## Existing CLI usage

The original workflow remains available:

```powershell
python main.py --role "Security Engineer" --location "Zurich, Switzerland" --max-jobs 10
python main.py --scrape-only
python main.py --analyze-only
```

A normal full CLI run analyzes only jobs scraped in that run. `--analyze-only`
intentionally analyzes all JSON files currently in `data/`.

## Database behavior

On backend startup, SQLAlchemy creates any missing tables and imports existing
raw JSON files. Importing repeatedly is safe:

- LinkedIn locale/tracking URLs are normalized to one canonical job URL.
- Identical title, company, location, and description content is merged even
  when LinkedIn and an employer ATS provide different URLs.
- Existing jobs update `last_seen` instead of creating duplicates.
- URL-less jobs use a deterministic hash of title, company, location, and
  description.
- Analysis results are append-only and retain their candidate-profile snapshot,
  model, score, breakdown, strengths/gaps, run, timestamp, and errors.
- A job search reuses a successful score only when the structured profile, CV
  evidence hash, and search controls are exactly unchanged.
- Raw CV text is stored separately and stays server-side. Analysis snapshots
  include only a SHA-256 identity for the CV evidence, not its raw contents.
- Generated cover letters are versioned by generation; edits update the selected
  generated letter.

Existing pre-upgrade binary verdicts remain in history but do not have a numeric
score. The next end-to-end search scores the listings it discovers with the new
structured model.

To reset only local web state, stop the backend and delete `jobbot.db`. On the
next startup the schema is recreated and current raw JSON files are reimported.

## Tests

Run backend tests:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest -q
```

Type-check and build the frontend:

```powershell
Set-Location frontend
npm run typecheck
npm run build
```

The test suite covers URL/content deduplication, idempotent JSON import,
structured profile and control persistence, score thresholding, deterministic
hard filters, DOCX text extraction, cover-letter persistence, append-only
analysis history, and application workflow updates.

## Implementation assumptions

- Jobbot is a single-user, local application and should run with one Uvicorn
  worker. The in-process run lock prevents simultaneous job searches.
- SQLite is the source of truth for dashboard state; raw JSON remains a private,
  replayable scraper artifact.
- The scraper uses public LinkedIn guest endpoints without authentication.
  LinkedIn can change or throttle these endpoints, so use the tool responsibly
  and review applicable terms.
- Greenhouse and Lever adapters use public company-board APIs without
  authentication. Configure only boards that are intended for public access.
- Gemini requests are paced according to `ANALYZER_DELAY_SECONDS` in `config.py`.
- Schema upgrades are additive SQLite bootstrap migrations because this local
  project does not yet use Alembic.
