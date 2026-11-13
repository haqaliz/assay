# Product Hunt launch package — Assay v0.1.0

Status: **draft package ready; the Product Hunt listing is not created.** The repo, PyPI release and
GitHub Pages site are live. This file gives you the copy, gallery, thumbnail, first comment, FAQ and
checklist. You create the PH draft and publish from your account.

## Listing fields

| Field | Value |
|---|---|
| **Name** | Assay |
| **Tagline** (56/60) | Execution-grounded security verifier for AI agent skills |
| **Description** (230/500) | Assay runs an AI agent skill in a sandbox on macOS or Linux against a real agent, captures what it actually did, and checks it against what it claims to do. Signed evidence, honest verdicts, and an audit gate. Open source, v0.1.0. |
| **Website** | https://haqaliz.github.io/assay/ |
| **GitHub** | https://github.com/haqaliz/assay |
| **PyPI** | https://pypi.org/project/assayhq/ |
| **Pricing** | Free · Open source (Apache-2.0) |
| **Topics** | Developer Tools · Security · Artificial Intelligence |
| **Makers** | Ali Haqiqi (`aliz`) |
| **Hunter** | Self-hunt is fine; a hunter is optional, not required. Do not pay for upvotes. |

## Gallery (upload in this order; 1270×760 each)

1. `docs/launch/assets/01-slide.png` — hero: logo, name, tagline, what it is.
2. `docs/launch/assets/02-slide.png` — why: static scan vs model opinion vs an Assay run.
3. `docs/launch/assets/03-slide.png` — how: ingest → run → capture → assess → attest.
4. `docs/launch/assets/04-slide.png` — honest verdicts: CLEAN/FLAGGED/MALICIOUS/UNVERIFIED.
5. `docs/launch/assets/05-slide.png` — try it: install, commands, links.

**Thumbnail:** `docs/launch/assets/thumbnail-240.png` (240×240).

**Video:** optional. The gallery is enough for a first launch; a 30–60s terminal video would be a
nice upgrade, but do not fake one. The current static gallery is real product output.

## Maker first comment

Post this as the first comment immediately after launch:

```text
Hi Product Hunt — I'm Ali, the maker.

I built Assay because "is this AI agent skill safe?" is usually answered by a static scan or a
model's opinion. Assay runs the skill in a sandbox on macOS or Linux against a real agent, captures
what it actually did, and checks that against what the skill declares. The verdict is backed by a
signed record a third party can verify offline.

v0.1.0 is open source on PyPI. It covers Claude Code/OpenClaw skills and Cursor rules; MCP has an
inspector and a conservative report. It does not claim a skill is safe: CLEAN means the run matched
the declared scope, and UNVERIFIED is never a pass.

macOS and Linux today (Linux has no sandbox network yet); Windows via WSL2. No web app; MCP runs
are macOS-only for now. I'd especially value feedback on the verdict model and the audit workflow.
Ask me anything.
```

## FAQ (use in replies or the listing)

**What does Assay actually do?**
It runs an agent skill in a sandbox on macOS or Linux against a real model, records every file,
network, shell and instruction event, and diffs that observed behavior against what the skill says it
will do. The result is a verdict plus a signed, replayable record.

**Is this another static scanner?**
No. A scan or a model can flag a candidate. Only the sandboxed, observed run assigns a verdict above
`UNVERIFIED`.

**Does CLEAN mean the skill is safe?**
No. `CLEAN` means the run matched the declared scope. It is per-run, not a guarantee. `UNVERIFIED` is
never a pass.

**What platforms are supported?**
macOS and Linux for `assay check`; Linux uses `bubblewrap` with no sandbox network, so `http_get`
fails closed. Windows via WSL2. MCP runs are macOS-only for now; native Windows is not supported.
Python 3.12+.

**Do I need an API key?**
No for `assay triage` or `assay mcp`. A sandboxed `assay check` needs a provider: BYOK Anthropic or
an OpenAI-compatible endpoint, including a local Ollama model with no key.

**What about MCP?**
`assay mcp` starts a stdio server, lists tools and shows denials. `assay mcp-report` runs a task with
the server's tools and reports `UNVERIFIED`/`FLAGGED`. A manifest declares startup, not behavior, so
there is no `CLEAN`/`MALICIOUS` server claim and no signed server bundle yet.

**Is it free?**
Yes, Apache-2.0. Donations are optional; there is no paid tier or hosted service.

**Has it been audited?**
A private own-skill dry run was reviewed privately on 2026-11-10: 21 signed bundles verified, 12/15
runs decided, no `HIGH`, no `MALICIOUS`. A public third-party audit still needs an independent
reviewer and the disclosure window. Do not call the product "audited" in the listing.

## Launch checklist

### Before launch

- [ ] Create the Product Hunt draft; add name, tagline, description, topics, website, GitHub, PyPI.
- [ ] Upload the five gallery images in order and the 240×240 thumbnail.
- [ ] Add the maker profile and the first comment.
- [ ] Choose a Tuesday–Thursday launch (12:01 AM PT), avoiding US Thanksgiving (Nov 26, 2026) and
      late-December holidays.
- [ ] Re-read the listing against the "do not say" list below.
- [ ] Ask 5–10 people for honest feedback on the draft; do **not** ask for upvotes.
- [ ] Prepare replies for the first 12 hours; know the limits and the Linux/MCP answer.
- [ ] Optional: set the GitHub social preview to `assets/assay-demo.png` (manual, repo settings).
- [ ] Optional: a custom domain; `haqaliz.github.io/assay` works.

### Launch day

- [ ] Publish at 12:01 AM PT; post the first comment immediately.
- [ ] Share on LinkedIn/X with a personal note; link the PH page after it is live.
- [ ] Reply to every substantive comment; link the README/PyPI for setup.
- [ ] Watch GitHub issues for install problems.
- [ ] Do not ask for upvotes, trade votes, or use engagement pods. Ask for feedback.

### After launch

- [ ] Capture the install friction and the top three questions.
- [ ] Open issues for real bugs; label `help wanted` where useful.
- [ ] Follow up with the public-audit reviewer call (issue #31) if there is interest.
- [ ] Do not overclaim the results in a retro.

## Do not say

- "Assay makes AI agent skills safe." It does not.
- "Audited" or "security certified." The public audit is not complete.
- "Malware detector" or "antivirus." It is a per-run behavior verifier.
- "Linux is fully supported." `assay check` works on Linux, but there is no sandbox network
  (`http_get` fails closed) and MCP runs are macOS-only.
- "MCP is verified." The report is `UNVERIFIED`/`FLAGGED`; there is no `CLEAN`/`MALICIOUS` server
  claim.
- "Replaces code review." It is a complement.

## Assets and regeneration

| Asset | Path |
|---|---|
| Hero slide | `docs/launch/assets/01-slide.png` |
| Why slide | `docs/launch/assets/02-slide.png` |
| How slide | `docs/launch/assets/03-slide.png` |
| Verdicts slide | `docs/launch/assets/04-slide.png` |
| Try slide | `docs/launch/assets/05-slide.png` |
| Thumbnail | `docs/launch/assets/thumbnail-240.png` |
| Source HTML/CSS | `docs/launch/src/slides.html`, `slides.css` |

Regenerate locally (macOS, Chrome, ImageMagick):

```sh
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
  --window-size=1270,3800 \
  --screenshot=/tmp/assay-launch.png \
  "file://$PWD/docs/launch/src/slides.html"

for i in 1 2 3 4 5; do
  y=$(( (i - 1) * 760 ))
  magick /tmp/assay-launch.png -crop 1270x760+0+$y +repage \
    "docs/launch/assets/0${i}-slide.png"
done

rsvg-convert -w 1026 assets/assay-logo.svg -o /tmp/assay-logo.png
magick /tmp/assay-logo.png -gravity center -crop 771x771+0+0 +repage \
  -resize 240x240 docs/launch/assets/thumbnail-240.png
```

## Risks and honest gaps

- **CLI, not a web app.** Product Hunt traffic may not install a Python CLI. The gallery and first
  comment must make that clear; the site is the demo.
- **Linux is partial.** `assay check` runs under `bubblewrap`, but the sandbox has no network
  (`http_get` fails closed) and MCP runs are macOS-only. Say that plainly.
- **No public audit yet.** The private dry run is signed; a public finding still needs a reviewer and
  disclosure. Do not imply certification.
- **No video.** The gallery is real output; a terminal video would be a plus, not a requirement.
- **No traction proof.** The launch is a cold start; the story is the execution-grounded method and
  the honesty of the limits, not user numbers.

## Recommendation

Use this package to create the PH draft and review it once. The listing is ready when the gallery,
thumbnail, copy and first comment are in place; the product itself is live. A custom domain and a
video are optional upgrades, not blockers.
