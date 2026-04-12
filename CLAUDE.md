# JobAutoApply - Project Memory

## What This Tool Is
JobAutoApply is a **pure Python CLI tool** that scrapes UK job boards (Reed, Indeed, LinkedIn), generates ATS-compliant tailored CVs and cover letters using Claude, and walks the user through applications one at a time in the terminal. No web app, no dashboard, no browser UI.

## 12 Hard Rules (Non-Negotiable)
1. **Pure Python CLI.** No web framework. No HTTP server. No dashboard. No browser UI.
2. Generated CVs MUST be **single column**. No tables, no text boxes, no columns.
3. Generated CVs MUST place **all content in the document body**. Never in DOCX headers or footers.
4. Generated CVs MUST use **Arial font** (11pt body, 14pt sections, 18pt name).
5. Generated CVs MUST use **exact standard section labels**: 'Personal Statement', 'Work Experience', 'Education', 'Skills', 'Certifications', 'Languages', 'References'.
6. Generated CVs MUST use **British English spelling**.
7. Generated CVs MUST be **at most 2 pages**.
8. Generated CVs MUST end with **'References available on request'**.
9. The AI MUST **never invent experience, skills, certifications, or qualifications** not in the Master CV.
10. All scraping MUST run locally with **randomised delays (3-8 seconds)** and a hard cap of **200 requests per source per session**.
11. API keys MUST be stored in **.env** and never committed to git.
12. The tool MUST be invokable as a single command: **`jobtool <subcommand>`**.

## Locked Tech Stack
| Component | Library | Purpose |
|-----------|---------|---------|
| Language | Python 3.11+ | Core language |
| CLI framework | Typer | Command parsing, subcommands, help text |
| Terminal UI | Rich | Colours, tables, prompts, progress bars |
| HTTP | httpx | Reed API and REST calls |
| Browser automation | Playwright (Python) | Indeed and LinkedIn scraping |
| AI | anthropic (official SDK) | Claude API for CV tailoring |
| DOCX rendering | python-docx | Strict ATS-compliant DOCX generation |
| PDF rendering | LibreOffice headless (subprocess) | DOCX-to-PDF conversion |
| Database | sqlite3 (stdlib) | Local persistence, zero-setup |
| Data validation | Pydantic v2 | Master CV schema validation |
| Config / .env | python-dotenv | Environment variable loading |
| Retries | tenacity | Exponential backoff for API calls |

## Folder Structure
```
jobtool/
├── jobtool/                 # main package
│   ├── __init__.py
│   ├── __main__.py          # python -m jobtool entry point
│   ├── cli.py               # Typer commands
│   ├── config.py            # .env loading, paths
│   ├── db.py                # SQLite schema + queries
│   ├── models.py            # Pydantic models (Job, MasterCV, Application)
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── base.py          # Scraper protocol
│   │   ├── reed.py          # Reed API client
│   │   ├── indeed.py        # Playwright-based Indeed scraper
│   │   └── linkedin.py      # Playwright-based LinkedIn scraper
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── tailor.py        # Claude CV + cover letter generation
│   │   └── prompts.py       # System and user prompt templates
│   ├── renderer/
│   │   ├── __init__.py
│   │   ├── docx_renderer.py # ATS-compliant DOCX renderer
│   │   └── pdf.py           # LibreOffice DOCX-to-PDF
│   └── review.py            # Interactive review loop
├── tests/
├── docs/                    # Planning documents
├── .env.example
├── pyproject.toml           # Poetry or uv project definition
└── README.md
```

## Data Directory Layout (~/.jobtool/)
```
~/.jobtool/
├── master-cv.json           # Source of truth Master CV
├── jobtool.db               # SQLite database
├── applications/            # Generated outputs
│   └── <company>-<role>-<date>/
│       ├── cv.docx
│       ├── cv.pdf
│       ├── cover-letter.docx
│       └── cover-letter.pdf
├── browser-contexts/        # Playwright persistent contexts
│   ├── indeed/
│   └── linkedin/
└── logs/
    ├── error.log
    └── scrape.log
```

## Critical Path
**The ATS-compliant DOCX renderer is the most important module.** Build it on Day 2 and validate against Jobscan before anything else. A non-compliant CV is useless.

### Build Sequence
- **Day 1:** Project setup, dependencies, SQLite schema, Master CV loader
- **Day 2 (CRITICAL):** ATS-compliant DOCX renderer. Validate against Jobscan before moving on.
- **Day 3:** Reed API integration + Claude API integration for CV/cover letter generation
- **Day 4:** Indeed and LinkedIn scrapers using Playwright
- **Day 5:** Interactive 'review' CLI loop, application tracking, final testing

## User Context
- UK-based on a **Graduate (Post-Study Work) visa** with 2 years remaining
- MSc Advanced Computer Science from University of Hertfordshire
- All CVs must follow **UK conventions**: British English, Personal Statement (not Professional Summary), 2 pages max, no photo/DOB, "References available on request"

## AI Generation Rules
- NEVER invent experience, skills, certifications, or qualifications not in the Master CV
- Use the `relevantFor` field in workExperience to decide what to include
- Mirror exact terminology from the job description
- Use British English spelling throughout
- Quantify achievements where source data allows

## Sprint 1 Acceptance Criteria
Sprint 1 is complete when ALL of the following are true:
1. `jobtool init` creates the data directory and SQLite schema
2. `jobtool scrape reed 'data entry'` fetches at least 20 jobs and saves to SQLite
3. `jobtool generate <job_id>` calls Claude and produces tailored CV DOCX + cover letter
4. Generated CV passes Jobscan with zero critical parse errors
5. Generated CV opens cleanly in Microsoft Word with no formatting issues
6. `jobtool review` walks user through pending jobs one at a time

---

## Progress Log

### Day 1 - Foundations (COMPLETE)
**Date:** 2026-04-11

**Completed:**
- [x] Read all 8 planning documents
- [x] Created CLAUDE.md with project memory
- [x] Environment checks: Python 3.10.11 (works), LibreOffice NOT installed (needed Day 2)
- [x] Created pyproject.toml with all dependencies
- [x] Created complete folder structure
- [x] Implemented jobtool/models.py with Pydantic v2 models:
  - PersonalDetails, WorkExperience, Education, Skills, Certification, Language, Project
  - MasterCV (full schema)
  - Job (scraped job)
  - Application (generated application)
  - TailoredCV (AI output)
- [x] Implemented jobtool/db.py with SQLite schema and CRUD:
  - jobs table with de-duplication by source + external_id
  - applications table
  - All query functions
- [x] Implemented jobtool/config.py for .env loading and path management
- [x] Implemented jobtool/cli.py with Typer:
  - `jobtool init` - creates ~/.jobtool/ and SQLite schema
  - `jobtool master-cv validate` - validates Master CV JSON
  - `jobtool master-cv edit` - opens CV in $EDITOR
  - Stub commands for remaining features (Day 3-5)
- [x] Created .env.example template
- [x] Created .gitignore
- [x] Created stub files for scrapers, ai, renderer modules
- [x] Package installs and runs: `pip install -e .`
- [x] Both init and validate commands tested and working

**Files Created:**
- pyproject.toml
- .env.example
- .gitignore
- jobtool/__init__.py, __main__.py
- jobtool/cli.py, config.py, db.py, models.py, review.py
- jobtool/scrapers/__init__.py, base.py, reed.py, indeed.py, linkedin.py
- jobtool/ai/__init__.py, prompts.py, tailor.py
- jobtool/renderer/__init__.py, docx_renderer.py, pdf.py
- tests/__init__.py

**Notes:**
- Windows console encoding required ASCII-safe output (no Unicode symbols)
- Using `legacy_windows=True` in Rich Console for compatibility

---

### Day 2 - ATS-Compliant DOCX Renderer (COMPLETE)
**Date:** 2026-04-11

**Completed:**
- [x] Implemented jobtool/renderer/docx_renderer.py with full ATS compliance:
  - Single column only (no Tables) - VERIFIED
  - Arial font (11pt body, 14pt headings, 18pt name) - VERIFIED
  - All content in body (no headers/footers) - VERIFIED
  - Exact section labels (Personal Statement, Work Experience, etc.) - VERIFIED
  - Solid round bullets (Unicode U+2022) - VERIFIED
  - 2cm margins - VERIFIED
  - Ends with "References available on request" - VERIFIED
- [x] Created test fixture: tests/fixtures/sample-master-cv.json
- [x] Implemented render_cv() and render_cover_letter() functions
- [x] Implemented jobtool/renderer/pdf.py with LibreOffice detection
- [x] Added `jobtool render-test` command for manual testing
- [x] Created 10 regression tests in tests/test_renderer.py - ALL PASSING
- [x] Generated sample CVs for both test fixture and user's Master CV

**Generated Files:**
- test-output/John-Smith-data-entry-clerk-2026.docx (from fixture)
- test-output/Gohar-Iqbal-software-developer-2026.docx (from user's CV)

**Files Modified/Created:**
- jobtool/renderer/docx_renderer.py (complete implementation)
- jobtool/renderer/pdf.py (LibreOffice wrapper with error handling)
- jobtool/cli.py (added render-test command)
- jobtool/models.py (fixed Pydantic deprecation warning)
- tests/fixtures/sample-master-cv.json
- tests/test_renderer.py (10 ATS compliance tests)

**USER ACTION REQUIRED:**
1. Open test-output/Gohar-Iqbal-software-developer-2026.docx in Microsoft Word
2. Verify formatting visually (single column, Arial, proper headings)
3. Upload to https://www.jobscan.co/ to verify ATS parse success
4. Install LibreOffice for PDF conversion: `winget install TheDocumentFoundation.LibreOffice`

---

### Day 3 - Reed API + Claude Generation (COMPLETE)
**Date:** 2026-04-12

**Completed:**
- [x] Implemented jobtool/scrapers/reed.py using httpx
  - Full Reed API integration with pagination
  - Fetches job listings and full descriptions
  - Handles API authentication (Basic Auth)
- [x] Implemented jobtool/ai/tailor.py with Claude API
  - CV generation with relevantFor hints
  - Cover letter generation
  - Retry logic with tenacity
  - Post-generation validation (no invented experience)
- [x] Implemented `jobtool scrape` command (Reed working)
- [x] Implemented `jobtool list` command
- [x] Implemented `jobtool generate <job_id>` command
- [x] Tested end-to-end flow with real Reed jobs - WORKING!

**Test Results:**
```
jobtool scrape "data entry" --location London --max 5
# Scraped 5 jobs from Reed API

jobtool list
# Shows jobs with ID, title, company, salary, status

jobtool generate 4
# Generated CV + cover letter + PDFs for "Trainee Data Entry Clerk"
```

**Files Created/Modified:**
- jobtool/scrapers/reed.py (full implementation)
- jobtool/ai/tailor.py (Claude API integration)
- jobtool/cli.py (scrape, list, generate commands)
- jobtool/models.py (made Certification fields optional)

---

### Day 4 - Indeed + LinkedIn Scrapers (NEXT)

**TODO:**
- [ ] Implement `jobtool login` command for Playwright
- [ ] Implement jobtool/scrapers/indeed.py with Playwright
- [ ] Implement jobtool/scrapers/linkedin.py with Playwright
- [ ] Add de-duplication across sources
- [ ] Test with real Indeed/LinkedIn searches
