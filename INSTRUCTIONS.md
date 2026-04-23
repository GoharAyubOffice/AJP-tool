# JobAutoApply - Complete Usage Guide

## EASIEST WAY: Interactive Menu

Just run:
```bash
jobtool interactive
```

This opens a menu-driven interface where you can:
- Scrape jobs from Reed, Indeed, LinkedIn
- View jobs
- Generate CVs
- Review and apply
- Track history

No need to remember commands - just select options with numbers or arrows!

---

## Quick Start

### 1. Setup (One Time)

```bash
# Initialize the tool
jobtool init

# Validate your Master CV
jobtool master-cv validate

# Edit your Master CV if needed
jobtool master-cv edit
```

---

## Interactive Menu Options

The interactive menu (`jobtool interactive`) provides:

| Menu | What it does |
|------|--------------|
| 🔍 Scrape Jobs | Search Reed, Indeed, LinkedIn |
| 📋 List Jobs | View all scraped jobs |
| 📄 Generate CV | Create tailored CV for a job |
| ✅ Review & Apply | Loop through jobs, generate CVs, apply |
| 📊 History | View past applications |
| ⚙️ Setup | Configure Master CV, API keys |
| ❓ Help | Show instructions |

---

## LinkedIn Scraping (Full Process)

LinkedIn requires your existing Chrome browser to be open with remote debugging.

### Step 1: Open Chrome with Remote Debugging

**PowerShell Command:**
```powershell
$env:DEBUG_PROFILE = "$env:TEMP\chrome-jobtool-debug"
if (!(Test-Path $env:DEBUG_PROFILE)) { New-Item -ItemType Directory -Path $env:DEBUG_PROFILE | Out-Null }
Start-Process -FilePath "C:\Program Files\Google\Chrome\Application\chrome.exe" -ArgumentList "--remote-debugging-port=9222","--user-data-dir=$env:DEBUG_PROFILE"
```

Or for Brave browser:
```powershell
$env:DEBUG_PROFILE = "$env:TEMP\chrome-jobtool-debug"
if (!(Test-Path $env:DEBUG_PROFILE)) { New-Item -ItemType Directory -Path $env:DEBUG_PROFILE | Out-Null }
Start-Process -FilePath "C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" -ArgumentList "--remote-debugging-port=9222","--user-data-dir=$env:DEBUG_PROFILE"
```

### Step 2: Log into LinkedIn

In the Chrome window that opens:
1. Go to https://www.linkedin.com
2. Log in with your credentials
3. **Keep this Chrome window OPEN**

### Step 3: Scrape Jobs

**In a NEW terminal:**
```bash
# Scrape LinkedIn jobs
jobtool scrape "data entry" --location London --sources linkedin --max 25

# Scrape Indeed jobs (no Chrome needed)
jobtool scrape "data entry" --location London --sources indeed --max 25

# Scrape from multiple sources
jobtool scrape "data entry" --location London --sources reed,indeed,linkedin --max 20
```

### Step 4: List Jobs

```bash
# See all scraped jobs
jobtool list

# Filter by status
jobtool list --status pending

# Filter by source
jobtool list --source linkedin
```

---

## Generate CV and Cover Letter

### Generate for One Job

```bash
# Generate CV and cover letter for job ID 42
jobtool generate 42

# Custom output directory
jobtool generate 42 --output ./my-applications
```

### Generate for Multiple Jobs

```bash
# Review and generate CVs interactively
jobtool review

# Review only pending jobs (default)
jobtool review --status pending
```

**Review Loop Keyboard Shortcuts:**
```
o  - Open job URL in browser
s  - Mark as submitted, go to next
x  - Skip this job, go to next
n  - Next job (no status change)
p  - Previous job
e  - Open CV file in viewer
r  - Regenerate CV and cover letter
q  - Quit review loop
?  - Show help
```

---

## Apply to Jobs

### Quick Apply (Single Job)

```bash
jobtool apply "https://www.reed.co.uk/jobs/data-entry-clerk/12345"
```

### Track Application History

```bash
# All applications
jobtool history

# Last 7 days
jobtool history --week

# Only submitted
jobtool history --status submitted
```

---

## Common Workflows

### Complete Job Hunt Workflow

```bash
# 1. Open Chrome with remote debugging
# (Run the PowerShell command from Step 1 above)

# 2. Log into LinkedIn in Chrome
# (Keep Chrome window open)

# 3. In a new terminal, scrape jobs
jobtool scrape "data entry" --location London --sources reed,linkedin --max 30

# 4. List all jobs
jobtool list

# 5. Generate CV for a specific job
jobtool generate 5

# 6. Review jobs interactively
jobtool review

# 7. Mark as submitted after applying
# (Use 's' key in review mode, or update manually)
```

### Generate Multiple CVs

```bash
# Review loop - generates CVs one by one
jobtool review --status pending

# Or generate individually
jobtool generate 1
jobtool generate 2
jobtool generate 3
```

---

## Test the Renderer

```bash
# Generate a test CV from your Master CV
jobtool render-test --cv ~/.jobtool/master-cv.json --job-title "Data Entry Clerk"

# Also generate PDF (if LibreOffice is installed)
jobtool render-test --pdf
```

---

## Master CV Management

```bash
# Validate Master CV
jobtool master-cv validate

# Edit Master CV in text editor
jobtool master-cv edit
```

---

## Command Reference

| Command | Description |
|---------|-------------|
| `jobtool interactive` | Launch interactive menu (recommended!) |
| `jobtool init` | Initialize data directory and database |
| `jobtool master-cv validate` | Validate Master CV JSON |
| `jobtool master-cv edit` | Edit Master CV in editor |
| `jobtool login indeed` | Login to Indeed (browser opens) |
| `jobtool login linkedin` | Login to LinkedIn |
| `jobtool login linkedin --connect-existing` | Connect to existing Chrome session |
| `jobtool scrape "query"` | Scrape jobs from all sources |
| `jobtool scrape "query" --sources reed,linkedin` | Scrape from specific sources |
| `jobtool list` | List scraped jobs |
| `jobtool list --status pending` | Filter by status |
| `jobtool generate <id>` | Generate CV for job |
| `jobtool review` | Interactive review loop |
| `jobtool apply <url>` | Quick apply to job URL |
| `jobtool history` | Show application history |
| `jobtool render-test` | Test CV renderer |
| `jobtool --help` | Show all commands |

---

## Troubleshooting

### LinkedIn "Browser not secure"

Use `--connect-existing` to connect to your existing Chrome where you're already logged in:
```bash
jobtool login linkedin --connect-existing
```

Make sure Chrome is running with remote debugging first (Step 1).

### LinkedIn scraping returns 0 jobs

1. Make sure Chrome is open with LinkedIn logged in
2. Use `jobtool login linkedin --connect-existing` first
3. Then run `jobtool scrape --sources linkedin`

### Indeed/LinkedIn not working

Reed API always works (public API). Indeed and LinkedIn require browser automation which may be blocked by their anti-bot measures. Use `jobtool login indeed` or `jobtool login linkedin --connect-existing` first.

---

## File Locations

| File | Location |
|------|----------|
| Data Directory | `~/.jobtool/` |
| Master CV | `~/.jobtool/master-cv.json` |
| Applications | `~/.jobtool/applications/<company>-<role>-<date>/` |
| Browser Contexts | `~/.jobtool/browser-contexts/` |
| Database | `~/.jobtool/jobtool.db` |

---

## Requirements

- Python 3.10+
- API keys in `.env` file (ANTHROPIC_API_KEY for AI CV generation)
- Chrome or Brave browser (for LinkedIn scraping)
- LibreOffice (optional, for PDF generation)

## Environment Variables

Create a `.env` file in the project root:
```
ANTHROPIC_API_KEY=your_api_key_here
REED_API_KEY=your_reed_api_key_here  # optional
```