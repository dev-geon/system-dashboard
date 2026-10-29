<p align="center">
  <a href="./README.md"><img src="https://img.shields.io/badge/English-30363D?style=for-the-badge" alt="Read in English" /></a>
  <a href="./README.ko.md"><img src="https://img.shields.io/badge/한국어-30363D?style=for-the-badge" alt="한국어로 읽기" /></a>
</p>

# System Dashboard

A **one-page HTML view of how a system is put together** for Codex and Claude Code.

Point it at a repository and it proposes the components it found, each with the file that proves it. You pick the views. It writes a Mermaid source file, checks it against diagram rules, and builds one HTML page: what changes (AS IS ▶ TO BE), by how much (a performance table with a real case per row), what the system looks like (a left-to-right tiered architecture), how a request flows (a flowchart with real use cases beside it), and which tickets the work belongs to.

<p align="center">
  <a href="#install"><img src="https://img.shields.io/badge/▶_INSTALL-OPEN-111111?style=for-the-badge&labelColor=5B5B5B" alt="Install System Dashboard" /></a>
  &nbsp;&nbsp;
  <a href="#what-it-produces"><img src="https://img.shields.io/badge/▶_OUTPUT-EXPLORE-1F6FEB?style=for-the-badge&labelColor=5B5B5B" alt="Explore the output" /></a>
</p>

<p align="center">
  <kbd>skills 1</kbd>
  <kbd>output single HTML file</kbd>
  <kbd>supports Codex + Claude</kbd>
  <kbd>Python 3.9+, no dependencies</kbd>
</p>

<p align="center">
  <a href="https://github.com/dev-geon/system-dashboard/blob/main/LICENSE"><img src="https://img.shields.io/github/license/dev-geon/system-dashboard?style=flat" alt="MIT license" /></a>
</p>

## A diagram someone can read the first time

Architecture diagrams fail in familiar ways: boxes labeled only with a type ("DynamoDB"), boxes connected to nothing, one master diagram that tries to show everything, arrows nobody agreed on, and behavior drawn as a one-way conveyor belt. This skill turns those lessons into rules a script can check, so the page is judged the same way every time instead of by eye.

The skill does not decide what to leave out. It proposes candidates with evidence; a person picks the views. A diagram generated from code alone is complete and has no point.

## What it produces

One HTML file in the reading order below. Dark and light themes follow the system setting.

| Order | Section | Notes |
|---|---|---|
| 1 | AS IS ▶ TO BE | Split panel. AS IS states what the current approach depends on and where it fails; TO BE states what the change makes possible. No numbers here |
| 2 | Performance table | Metric · AS IS · TO BE · change, plus an optional example column. Every number lives here; where each number came from is reported in the answer, not on the page |
| 2a | Migration map | Only when work moves from one project (repo) to another. AS IS project ▶ TO BE project, then one row per role: white card ─[ported · merged · source changed …]▶ blue card; what stays behind is a dashed empty card |
| 3 | Tabs | Named by chart type only: System architecture, Flowchart, Sequence diagram, Deployment architecture |
| 3a | System architecture | Tiers laid out left to right, cards with a type icon, a bold name and a type caption. New or changed parts are blue cards. Connectors are straight horizontal and vertical lines; one card has one exit that branches per target |
| 3b | Flowchart | Mermaid flowchart on the left; real use cases for each path on the right, matched by badge (A, B, C) |
| 4 | Jira | Ticket numbers linked to the tracker, with titles and types. Initiatives are highlighted |

There is no header block, no KPI tiles, and no footer. Tabs and pictures carry the page.

## Rules the checker enforces

`check_diagrams.py` reads the source and reports FAIL (blocks the build) or WARN (shown to a person):

- **Names, not just types.** Labels are `name · type`, for example `Orders Table · PostgreSQL`.
- **No orphans.** A box with no connector is removed or moved to the view where its role shows.
- **Arrows mean one thing each.** `-->` synchronous request, `-.->` asynchronous event, `==>` data flow. Lines without arrowheads fail.
- **Round trips go to sequence diagrams,** and message brokers are drawn per topic, not as one hub.
- **Two shape vocabularies.** Flowcharts use the standard flowchart symbols (terminal, process, decision, input/output, predefined process, store). Architecture uses people, apps and services, external systems, and stores; flowchart symbols in an architecture view fail.
- **Every flowchart path has a real example.** End terminals carry badges and each badge needs a case from logs, tests, experiments, or tickets.
- **Meaning on the page, sources in the answer.** File paths, `file:line`, commit hashes, and acceptance-criterion IDs are flagged on the page; the Jira section is the one place the page links to evidence, and every Jira key links to its own `/browse/<KEY>` address.
- **No word-for-word translation of engineering terms.** Korean pages use the terms engineers actually say (오버레이 for overlay, 포인트 읽기 for point read, 불일치 for divergence) instead of literal translations (덮기, 점 읽기, 발산), which readers cannot map back to the code.
- **Architecture shows TO BE only.** Mixing a component that is being replaced with the new structure is flagged, and so is a view too wide for the screen.
- **Migration maps stay at role level, ten pairs at most,** and each move uses a fixed word (포팅 · 바뀜 · 합침 · 원천 변경 · 새로 · 유지 · 폐기).

## Install

### Codex

```bash
codex plugin marketplace add dev-geon/system-dashboard
codex plugin add system-dashboard@system-dashboard
```

Start a new Codex task after installation so the bundled skill is discovered.

### Claude Code

```text
/plugin marketplace add dev-geon/system-dashboard
/plugin install system-dashboard@system-dashboard
```

No configuration is required. The scripts use only the Python standard library. The page loads Mermaid and Pretendard from a CDN; offline, the Mermaid source is shown with a note.

## Usage

The skill triggers on requests like "draw this repo's architecture", "make an AS IS / TO BE structure page", or "turn this flow into a flowchart for the team docs", even without the word "dashboard". Progress and KPI dashboards are out of scope.

```text
Draw the architecture of this repository as a one-page dashboard for new developers.
We are moving mail sending out of the order API into a worker; show AS IS / TO BE,
the p95 numbers from load-test/report-2026-10.json, and the order flow with a sold-out case.
Initiative is SHOP-100 on https://example.atlassian.net.
```

Steps: ask who will read it and where to save the files (outside the repository being analysed) → scan the repository for components with evidence → you confirm views and use cases → write `dashboard.md` → `check_diagrams.py` until no FAIL → `build_dashboard.py` → open the page and check every tab.

## Repository structure

<details>
<summary>Show plugin files</summary>

```text
.agents/plugins/marketplace.json       # Codex Git marketplace entry
.codex-plugin/plugin.json              # Codex plugin manifest
.claude-plugin/plugin.json             # Claude Code plugin manifest
.claude-plugin/marketplace.json        # Claude Code marketplace entry
skills/system-dashboard/
├── SKILL.md                           # The skill: procedure, notation summary, what it never does
├── agents/openai.yaml                 # Codex skill metadata
├── references/diagram-rules.md        # D1–D9 (D8 retired), P1–P3: labels, orphans, arrows, round trips, brokers, TO BE only
├── references/symbols.md              # F1–F4 flowchart symbols, architecture shapes, view kinds
├── references/layout.md               # Page layout, tokens, L1–L7 (AS IS/TO BE, use cases, tables, Jira)
├── assets/dashboard.template.html     # Page shell: theme tokens, tabs, architecture renderer
├── assets/dashboard.example.md        # Starting source with every section
├── scripts/check_diagrams.py          # Linter: FAIL/WARN with line numbers, exit code 1 on FAIL
└── scripts/build_dashboard.py         # Builder: re-runs the checks, then writes the HTML
```

</details>

## Sources

- Rules D1–D8 summarize Billy Pilger's (Ilograph) "More common mistakes to avoid when creating system architecture diagrams" and the Hacker News discussion, via the Korean write-up on WikiDocs.
- Flowchart symbols follow the basic ISO 5807 set as summarized by Boardmix.

## License

MIT
