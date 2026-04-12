# JobAutoApply - Project Handover Document

**Last Updated:** 2026-04-12
**Current Sprint:** Sprint 1 (5-day build)
**Current Day:** Day 3 COMPLETE, ready for Day 4 (Indeed/LinkedIn scrapers)

---

## 1. Project Overview

**What is JobAutoApply?**
A pure Python CLI tool that:
1. Scrapes UK job boards (Reed, Indeed, LinkedIn)
2. Generates ATS-compliant tailored CVs and cover letters using Claude AI
3. Walks the user through applications one at a time in the terminal

**Key Constraint:** This is a CLI-only tool. NO web framework, NO HTTP server, NO dashboard, NO browser UI. If you find yourself reaching for Flask, FastAPI, Next.js, or React - STOP. That is scope creep.

**Target User:** Gohar - UK-based on a Graduate visa, MSc Computer Science, looking for data entry/admin/junior dev roles.

---

## 2. Document References

All planning documents are in the repo root as `.docx` files. Read them in this order:

| Order | File | Purpose |
|-------|------|---------|
| 1 | 00_BuildOrder_JobAutoApply.docx | Master index, tech stack, hard rules |
| 2 | 01_PRD_JobAutoApply.docx | Product requirements |
| 3 | 07_MasterCV_System.docx | **CRITICAL** - ATS rules, JSON schema, AI prompts |
| 4 | 02_TRD_JobAutoApply.docx | Technical requirements (TR-1 to TR-51) |
| 5 | 03_TDD_JobAutoApply.docx | Architecture, module design |
| 6 | 04_UserStories_JobAutoApply.docx | Features with acceptance criteria |
| 7 | 05_SprintPlan_JobAutoApply.docx | Day-by-day build plan |
| 8 | 06_CLI_Spec_JobAutoApply.docx | Command interface spec |

Also read: `master-cv-starter.json` - the Master CV JSON schema

---

## 3. Tech Stack (LOCKED - Do Not Change)

| Component | Library | Purpose |
|-----------|---------|---------|
| Language | Python 3.10+ | Core |
| CLI | Typer | Commands |
| Terminal UI | Rich | Colors, tables, panels |
| HTTP | httpx | Reed API |
| Browser | Playwright | Indeed/LinkedIn scraping |
| AI | anthropic SDK | Claude API |
| DOCX | python-docx | CV rendering |
| PDF | LibreOffice (subprocess) | DOCX-to-PDF |
| Database | sqlite3 (stdlib) | Local storage |
| Validation | Pydantic v2 | Schema validation |
| Config | python-dotenv | .env loading |
| Retries | tenacity | API retry logic |

---

## 4. 12 Hard Rules (NON-NEGOTIABLE)

1. Pure Python CLI only - no web framework
2. CVs must be single column - no tables, no text boxes
3. All CV content in document body - never in headers/footers
4. Arial font only (11pt body, 14pt sections, 18pt name)
5. Exact section labels: Personal Statement, Work Experience, Education, Skills, Certifications, Languages, References
6. British English spelling
7. CVs max 2 pages
8. CVs end with "References available on request"
9. AI must NEVER invent experience/skills not in Master CV
10. Scraping: randomised 3-8s delays, max 200 requests/source/session
11. API keys in .env, never committed
12. Single command entry: `jobtool <subcommand>`

---

## 5. Project Structure

```
AJP-tool/
├── jobtool/                    # Main package
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py                  # Typer commands
│   ├── config.py               # .env and paths
│   ├── db.py                   # SQLite operations
│   ├── models.py               # Pydantic models
│   ├── review.py               # Interactive loop (stub)
│   ├── scrapers/
│   │   ├── base.py             # Scraper protocol
│   │   ├── reed.py             # Reed API (stub)
│   │   ├── indeed.py           # Playwright (stub)
│   │   └── linkedin.py         # Playwright (stub)
│   ├── ai/
│   │   ├── prompts.py          # AI prompt templates
│   │   └── tailor.py           # Claude calls (stub)
│   └── renderer/
│       ├── docx_renderer.py    # ATS-compliant DOCX ✓
│       └── pdf.py              # LibreOffice wrapper ✓
├── tests/
│   ├── fixtures/
│   │   └── sample-master-cv.json
│   └── test_renderer.py        # 10 ATS tests ✓
├── .env.example
├── .gitignore
├── CLAUDE.md                   # Project memory for AI
├── HANDOVER.md                 # This file
├── pyproject.toml
└── [planning .docx files]
```

---

## 6. Data Directory

User data stored at `~/.jobtool/`:
```
~/.jobtool/
├── master-cv.json              # User's Master CV
├── jobtool.db                  # SQLite database
├── applications/               # Generated CVs/cover letters
├── browser-contexts/           # Playwright sessions
│   ├── indeed/
│   └── linkedin/
└── logs/
```

---

## 7. Sprint Progress

### Day 1: Foundations ✅ COMPLETE
- [x] pyproject.toml with dependencies
- [x] Folder structure
- [x] Pydantic models (MasterCV, Job, Application)
- [x] SQLite schema and CRUD
- [x] config.py for .env loading
- [x] `jobtool init` command
- [x] `jobtool master-cv validate` command
- [x] Committed: `c198ab8`

### Day 2: ATS Renderer ✅ COMPLETE
- [x] docx_renderer.py with full ATS compliance
- [x] render_cv() and render_cover_letter()
- [x] pdf.py with LibreOffice wrapper
- [x] `jobtool render-test` command
- [x] Test fixture (sample-master-cv.json)
- [x] 10 regression tests - ALL PASSING
- [x] Committed: `0c1d8d8`

### Day 3: Reed API + Claude Generation ✅ COMPLETE
- [x] Implement reed.py scraper (full API integration)
- [x] Implement tailor.py with Claude API
- [x] Implement `jobtool scrape` command
- [x] Implement `jobtool list` command
- [x] Implement `jobtool generate <job_id>` command
- [x] End-to-end test PASSED - CV + Cover Letter + PDF generated

### Day 4: Indeed + LinkedIn Scrapers ✅ COMPLETE
- [x] `jobtool login indeed` command
- [x] `jobtool login linkedin` command
- [x] indeed.py with Playwright + persistent context + anti-detection
- [x] linkedin.py with Playwright + stronger anti-detection
- [x] Multi-source scraping support
- [x] De-duplication via database
- [x] 19 unit tests - ALL PASSING

### Day 5: Review Loop + Polish 🔜 NEXT
- [ ] Interactive review loop (`jobtool review`)
- [ ] `jobtool history` command
- [ ] `jobtool apply <url>` command
- [ ] Final testing and polish

---

## 8. Working Commands

```bash
# Install the tool
pip install -e .

# Initialise data directory
jobtool init

# Validate Master CV
jobtool master-cv validate

# Test the renderer (generates sample DOCX)
jobtool render-test --output ./test-output

# Test with PDF (requires LibreOffice)
jobtool render-test --output ./test-output --pdf

# Login to job boards (required for Indeed/LinkedIn)
jobtool login indeed
jobtool login linkedin

# Scrape jobs from sources
jobtool scrape "data entry" --location London --max 20
jobtool scrape "developer" --sources reed,indeed,linkedin --max 30

# List scraped jobs
jobtool list
jobtool list --status pending
jobtool list --source reed

# Generate CV and cover letter for a job
jobtool generate <job_id>

# Show help
jobtool --help
```

---

## 9. Environment Setup Required

### API Keys (.env file)
```
REED_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
ANTHROPIC_MODEL=claude-sonnet-4-6
```

### LibreOffice (for PDF)
```powershell
winget install TheDocumentFoundation.LibreOffice
```

### Master CV
Copy and edit:
```bash
cp master-cv-starter.json ~/.jobtool/master-cv.json
# Edit with real details
jobtool master-cv validate
```

---

## 10. Key Files to Read

If picking up this project:

1. **CLAUDE.md** - Project memory with rules and progress
2. **HANDOVER.md** - This file
3. **jobtool/models.py** - All data schemas
4. **jobtool/renderer/docx_renderer.py** - The critical ATS renderer
5. **jobtool/ai/prompts.py** - AI prompt templates for Day 3

---

## 11. Known Issues / Notes

1. **Windows Console:** Using `legacy_windows=True` in Rich for Unicode compatibility
2. **Python Version:** Built on 3.10.11 (works fine despite docs saying 3.11+)
3. **LibreOffice:** Not yet installed on user's machine - needed for PDF
4. **Master CV:** User still has placeholder values to fill in

---

## 12. Git History

```
0c1d8d8 Day 2: ATS-compliant DOCX renderer (CRITICAL PATH)
c198ab8 Day 1: Project foundations and CLI setup
6789f01 Docs Added
1b1934a first commit
```

---

## 13. Next Session Checklist

Before starting Day 3:

- [ ] User confirmed DOCX opens correctly in Word
- [ ] User confirmed Jobscan parses with zero errors
- [ ] User installed LibreOffice
- [ ] User filled in Master CV placeholders
- [ ] User created .env with REED_API_KEY and ANTHROPIC_API_KEY

Then proceed with:
1. Implement Reed API scraper (reed.py)
2. Implement Claude AI generation (tailor.py)
3. Wire up `jobtool scrape` and `jobtool generate` commands

---

## 14. Contact / Repository

- **Repository:** https://github.com/GoharAyubOffice/AJP-tool
- **Branch:** main
- **User:** Gohar (buttg on Windows)

---

*This handover document should be updated at the end of each day/session.*
