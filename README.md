# SentinelUpdate

**AI-Powered Pre-Update Risk Advisor for Linux Systems**

SentinelUpdate analyzes pending Linux package updates *before* you apply them,
scores their risk against your actual running system, explains the risk in
plain English, and creates a reversible safety snapshot — turning "update
and hope" into an informed, explainable decision.

> **Built for**
> Hackathon: *Integration of AI Capabilities in the Linux-Based OS Ecosystem*  
> Track: *AI at Application Level*  
> Problem Statement: *Open Innovation-Linux Based*  
> **C-DAC**

## Why this exists

Existing update tools (`apt`, `unattended-upgrades`) apply updates blindly,
with no awareness of what's actually running on your system. A routine
`apt upgrade` can silently break an NVIDIA driver, change a config format
underneath a running service, or require a reboot you didn't plan for —
and you only find out after something breaks.

## What makes this different

- **Two independent signal sources, not a black box.** A deterministic rule
  engine scores structural risk (kernel packages, active driver modules,
  version jumps). A separate AI layer reads the *actual changelog text* of
  each update for concrete risk indicators no rule could catch — and cites
  the exact line that justified its score. The AI never overrides the
  score; it only explains and adds bounded, cited evidence.
- **Explanations a human can actually use.** Every risk is translated into
  three plain-language parts — what's changing, what could concretely
  break, and what to do about it — instead of restating technical jargon
  like "kernel module conflict."
- **Nothing is ever auto-applied.** Every risky action — proceeding with an
  update, restoring a snapshot — requires explicit user confirmation.
  Snapshot restores default to a dry-run that shows the exact commands
  before anything executes.
- **Transparent about its own limits.** A visible status badge shows
  whether the AI layer is actually connected or running on its offline
  rule-based fallback — the tool never silently pretends to use AI when it
  isn't.
- **Works offline.** If no `GEMINI_API_KEY` is set, or the API is
  unreachable, the tool falls back to a deterministic explanation instead
  of failing — a real sysadmin tool can't depend on a live network call to
  function.

## Quick start

```bash
git clone https://github.com/shreyaya612/SentinelUpdate.git
cd SentinelUpdate
pip install -r requirements.txt

### Configure Gemini API
Create a `.env` file in the project root and add your Gemini API key.
Get your API key from [Google AI Studio](https://aistudio.google.com/apikey).
```env
GEMINI_API_KEY=your-key-here

# Web dashboard
python ui/app.py
# open http://localhost:5050

# or CLI
python main.py scan --demo
```
## Quick start (Ubuntu / WSL2)

> **Windows users:** this project depends on `apt`/`dpkg`, which don't exist
> natively on Windows. Run it inside **WSL2 with Ubuntu**, not native
> PowerShell/CMD.
>
> Install WSL2 if you haven't: `wsl --install -d Ubuntu` (from PowerShell)

**1. Get the project into your Linux home directory — not `/mnt/c/...`**

Running Python venvs directly on the Windows-mounted filesystem
(`/mnt/c/Users/...`) causes permission/performance issues (`ensurepip`
failures, missing `venv/bin/activate`). Keep a working copy inside WSL's own
filesystem instead:

```bash
cd ~
cp -r /mnt/c/Users/<you>/Desktop/SentinelUpdate ~/SentinelUpdate
cd ~/SentinelUpdate
```

**2. Install Python tooling (first time only)**

```bash
sudo apt update
sudo apt install python3-pip python3-venv -y
```

**3. Create and activate a virtual environment**

```bash
python3 -m venv venv
source venv/bin/activate
```

Your prompt should now show `(venv)` at the start. If `python3 -m venv venv`
fails with an `ensurepip` error, it's almost always because you're still on
`/mnt/c/...` — go back to step 1.

**4. Install dependencies and configure your API key**

```bash
python -m pip install -r requirements.txt
echo "GEMINI_API_KEY=your-key-here" > .env
```

**5. Run it**

```bash
python ui/app.py
# open http://localhost:5050 in your browser
```

Every time you come back to work on this later:

```bash
cd ~/SentinelUpdate
source venv/bin/activate
python ui/app.py
```

No API key? The tool still runs fully — it just uses rule-based
explanations instead of AI-generated ones (shown clearly in the UI's AI
status badge).

## Project Structure
<details>
<summary><b>View Project Structure</b></summary>
  
```text
SentinelUpdate/
├── scanner/
│   └── system_scanner.py
├── risk_engine/
│   └── risk_scorer.py
├── ai_layer/
│   ├── explainer.py
│   └── changelog_analyzer.py
├── rollback/
│   └── snapshot.py
├── ui/
│   ├── app.py
│   └── templates/
│       └── index.html
├── docs/
├── main.py
├── requirements.txt
├── README.md
└── LICENSE
```
</details> 

 ## How risk scoring works

1. **Structural signals** (deterministic, always computed): is this a
   kernel/driver/core-system package? Does it touch a currently loaded
   kernel module? Is it a major version jump?
2. **Semantic signals** (AI, optional "deep analysis" mode): the real
   package changelog is fetched and read by Gemini for concrete risk
   language — breaking changes, deprecations, required reboots — with a
   bounded (0–30) contribution and a citation back to the source text. If
   the changelog can't be fetched (offline, no network), this is shown
   explicitly rather than failing silently.
3. Combined score maps to **LOW / MEDIUM / HIGH**, and every explanation
   is split into three parts: what's changing, what could concretely
   break, and the recommended action — with the raw technical signals
   still available on demand for full auditability.

## Known limitations & honest scope

- Changelog fetching (`apt-get changelog`) requires network access to
  Ubuntu/Debian changelog servers; on a fully offline machine this step is
  skipped gracefully (and shown as such) and the tool falls back to
  structural signals only.
- The rule engine's package-category lists (kernel, driver, core-system)
  are a maintained seed list for the prototype, not an exhaustive database —
  a production version would maintain this against a real CVE/package feed.
- Snapshot restore generates a plan by default; actual execution
  (`execute=True`) requires explicit opt-in, since downgrading packages is
  itself a risk-bearing operation.
- Tested on Debian/Ubuntu (`apt`/`dpkg`) systems; other distributions
  (Fedora/RPM, Arch) are not currently supported.

## License

MIT — see [LICENSE](LICENSE). Third-party dependencies and their licenses
are listed in [`docs/THIRD_PARTY_LICENSES.md`](docs/THIRD_PARTY_LICENSES.md).
