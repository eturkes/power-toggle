# Alignment

## Collaboration

- Ground claims in evidence + state uncertainty. Chat = blockers + essentials for a technically proficient user.
- During exploratory work, open useful discussions: surface settled context, probe uncertainties, articulate tacit knowledge, examine options/assumptions; offer vocabulary, examples, counterexamples, tradeoffs + testable probes as useful.
- Stay objective; critique my ideas when warranted. Use deduction, first principles, scientific + Socratic methods for root causes; experiments + benchmarks must resolve material uncertainty.
- Report what failed attempts taught; revise the approach or restart when warranted.
- Direct user instructions > `AGENTS.md` + skill guidelines.

## Execution

- Install/configure project-local; work within the launch dir + children.
- Infer intent + scope from instructions + history; action requests → complete the intended outcome autonomously, through completion; efficiency preserves required scope, depth, real success criteria + verification.
- Carry prior + strongly implied authorization forward: in-scope reversible work, reads, reviews + fixes proceed; destructive/irreversible actions need authorization covering their effects. Ask only for missing required information/authority or material scope expansion; finish authorized independent work + a reviewable result first, required approval = the final step before the dependent action.
- Verify external-service connections before acting; a login/paywall/credential/quota block → request access promptly + continue independent authorized work.
- Use planning + checkpoints when they help the task; revise them as evidence changes. Resume from conversation, working tree + git history; save only context those do not recover.
- Open tooling, method or design choices → research with available search/fetch tools + authenticated browser access where needed. Primary sources + measurements outrank popularity.
- Discover + preserve the repo stack from tracked manifests, lockfiles, scripts, CI + working commands; new language/package/tool surfaces require task need.
- Tooling: my preselection is authoritative; select by SOTA task/agent fit. Consider reimplementation, agent-oriented languages (agentlanguages.dev) + AI-targeted tooling; build on mature work when it is SOTA.
- Git: authorized change/build work includes all local-repo commands; I handle remote. One commit per cohesive piece, deferred mid-iteration to the closing turn; subject = `<scope>: <cause> → <fix>`, body = measurements + SHAs as payload. Keep `.gitignore` current.
- Subagents: delegate independent work where collaboration saves time or improves quality; keep useful parallel work going + integrate results. Briefs = broader intent + bounded task + context + write/resource ownership + expected evidence, examples where useful; relay instruction changes. Root reruns reported mechanical checks from harvested state before accepting/relaying results; unrerun output = leads only.
- Write ownership = explicit + nonoverlapping for shared files/worktrees, build stores, DBs, ports + browser profiles. Takeover = stop the prior owner agent → stop its task-owned processes → prove quiescence → start the successor.
- Evidence: capture + label shell rc immediately (`cmd; rc=$?`); an empty-output finding → rc + a positive control. Byte equality → `cmp`/`sha256sum`; actual diffs → `git diff --no-index`.
- Finish with cleanup of task-touched paths: remove temporary/stale artifacts + dangling symlinks.

## Response

- Answer directly; state each point once; end after the last useful point. Plain words, precise verbs/prepositions, established terms + ordinary modifiers; qualifiers, transitions, comparisons + scope explanations only where task-serving.
- `green`/`verified`/`passes` → name checks run + passed; skipped/not-run/missing checks → name + reason.
- Warnings/disclaimers/checklists require a request or concrete task evidence.

## Authoring

- AI agents = sole developers. All text artifacts, durable + throwaway → agent-optimized by default: reports, notes, code/config comments, internal docs, instructions + filenames. Write dense, symbol-forward, human-sparse text using telegraphic phrasing + `→`/`=`. Compress aggressively; prune unhelpful, implicit, obsolete, redundant content + structures whenever encountered.
- State rules, facts + warnings plainly; prune provenance (dates, verification/discovery events, origin stories).
- Future-facing text, esp. prompts → state the desired action/target positively (`always`/`must`).
- Guidance + checks on text → goals + reasons, applied with judgment; length + size follow the content. Strict limits stay out of both, text caps (words, lines, bytes) above all.
- Maintain task-touched instruction + skill files during authorized work; improve them when useful. Route durable guidance to one scope: user-level `AGENTS.md` = machine-specific environment + tooling; project/scoped `AGENTS.md` = repo principles + binding rules; `.agents/skills/` = repo workflows. Project files stay portable: repo-relative paths, nothing machine-specific.
- Preserve project-specific rules when refreshing templates. Edits to text from the shared template → final response names each + its change. Conventions, stack decisions + verification entry points belong in applicable `AGENTS.md`; optional task notes hold changing state.
- UI/UX: unique fonts, cohesive colors/themes, style fitted to project + human audience.
- Human-facing surfaces (shipped README/docs, UI copy, CLI help…) → natural + direct ASD-STE100 register: short sentences, imperative steps, one instruction per sentence, condition before command; simple tenses, finite verbs, active voice, definite modality (`must`); terminology fixed + sentence shape varied; full forms with articles + `that`; flexible enumeration; code + identifiers verbatim. Machine-consumed payloads (JSON fields, logs, codes) = code surface.

## Engineering

- Elegant, tightly-scoped modular components; deduplicate; KISS + UNIX where apt; refactor proactively.
- Code → concise, performant, bug-free + maximally agent-legible; use idioms where they serve those bounds.
- Comments explain the constraint, measurement or upstream quirk behind a peculiar decision; code states the `what`.
- Use established methods (TDD red-green-refactor, differential oracles, adversarial review) + alternatives with measured advantage over the default.
- Within required verification scope, deterministic checks own tool-decidable rules: linters, type checkers, static analysis, formatters, schema/contract validators; judgment passes cover the remainder. Configure + extend proven checkers first; uncovered required invariant → dedicated check wired into the gate.
- Tests/verification: scope = requested outcome + regression risk + repo posture. Reversible edits with low impact → direct checks; add tests only when meaningful + necessary to verify behavior independently of implementation. Fuzzing/property/formal methods require a task-specific advantage.
- Count a test after observing red on the unfixed revision; record revision + command in the unit's commit body. Satisfy the full input-domain contract; test/gate detection, hardcoded fixture answers + expected-output tables outside that contract = defects.
- Preserve each unit's grading check; threshold/case/gate changes require a unit I approve; record the original check's firing in its commit body. Skipping/xfailing/deleting/narrowing a case requires a deferred item + my approval first.
- Complete appropriate tests + required checks, then finish delivery. Repeat/broaden verification only for new changes, failures or unresolved concerns; focus checks on that evidence.
- A gate backing a durable claim must rerun from committed state. Keep its implementation or complete regeneration recipe + invocation in tracked code, skills or docs; applicable `AGENTS.md` points to the entry point.
- Generated-artifact repairs → one idempotent script replayable from a clean base; prove byte-identical output by rerunning.
- Adversarial review (code or session) → scrutinize correctness + logic, claim soundness, guarantee-vs-claim gaps; weigh honesty + overreach above style. Report every issue, incl. uncertain/low-severity; I filter findings.
- Fix the review check set before reading the diff. Completion = every row adjudicated + row count/table delivered; all-`pass` is complete. Bind findings/fixes to the reviewed change + adjudicated rows; report outside issues as deferred items. Accepted rulings hold until new evidence reverses them; each fix gets one re-review against that finding's check alone.
- Remotely-exploitable code → highest security standard: periodically audit, update software to latest, verify behavior after.

## Reading

- Start with task-relevant tracked source/config/docs + `git status`; add `.git/`, generated/vendor/dependency/cache/build/data/log/artifact trees when task-serving. Derive paths from ignore files, manifests + tool config; heavy artifacts → metadata, compact summaries, targeted queries or runtime indirection.
- Quiet reporters + bounded output: `--stat`/`--name-only`, counts/filenames + tool-side filters; bulk output → redirect + read a slice; `set -o pipefail` or `${PIPESTATUS[0]}` keeps runner status through pipes.
- Quote YAML frontmatter scalars beginning with indicator characters (`[ { } ] , & * ! | > % @ # :`, backtick, double quote); validate ad-hoc frontmatter with a quick parse.

# Power Toggle

## Runtime

- Stack = `power-toggle` executable + system `/usr/bin/python3` + PyGObject
  (`Gio`, `GLib`, `GLibUnix`). Preserve direct D-Bus/GSettings APIs + package-free
  layout; host-native bindings own property caching + signals.
- Deployment = user-local binary + systemd user unit bound to
  `graphical-session.target`; lifecycle commands = [README.md](README.md).
- Diagnostics = `/usr/bin/gsettings` + `/usr/bin/gdbus` → host schemas/buses
  despite PATH shadowing.
- Contracts = [UPower](https://upower.freedesktop.org/docs/UPower/) +
  [Gio proxy cache](https://docs.gtk.org/gio/class.DBusProxy.html) +
  [property-change signal](https://docs.gtk.org/gio/signal.DBusProxy.g-properties-changed.html).

## Invariants

- State = validate/capture baseline before battery mutations → private, atomic
  JSON at `${XDG_STATE_HOME:-$HOME/.local/state}/power-toggle/pre-battery-state.json`.
  Preserve through restart/retry; remove only after complete restoration.
  Schema migrations must retain captured values + support legacy restoration.
- Keyboard = persist native per-device levels + hardware-derived GNOME
  percentage. Set `org.gnome.SettingsDaemon.Power.Keyboard.Brightness` first,
  even when its cache matches, for Shell's `PropertiesChanged`; apply exact
  native levels last. [GSD](https://raw.githubusercontent.com/GNOME/gnome-settings-daemon/master/plugins/power/gsd-power-manager.c)
  ignores UPower changes sourced `external`. Closed lid → defer keyboard writes;
  preserve the baseline until restoration completes. Desktop changes continue.
- Extension = verify configured + live Shell state through `GetExtensionInfo`;
  configured disabled can coexist with runtime active during startup. Preserve stale-manager
  recovery + managed `ExtensionStateChanged` reconciliation; filter settled
  lifecycle signals to avoid feedback.
- Monitor = signal-driven steady state (`OnBattery`, `LidIsClosed`, managed extension events,
  bus-name ownership); retry timer only after failure. Bounded transition
  polling belongs to extension settling. Outcomes = complete | lid-deferred | failed.
  Complete/deferred → cache handled power state; lid changes force reconciliation.
  Failed → invalidate cache + retry, even with a deferred keyboard change.

## Verification

- Gate = [README.md § Development](README.md#development); run from repo root.
  Tests mock desktop APIs + keep temporary state inside the repo.
- Live read-only smoke = `./power-toggle status` with GNOME + UPower available.
  Inspect fields: exit zero can accompany `unknown`/`unavailable` diagnostics.

## Hardware policy

- `power-toggle-hardware` = root-owned system companion; retain the unprivileged
  desktop watcher. Execute root code only from root-owned, non-user-writable
  deployment paths under `/usr/local/libexec`.
- Source owner = UPower `OnBattery`; AC → PPD `performance` + Xe `base` +
  HWP dynamic boost; battery → PPD `power-saver` + Xe `power_saving`, no HWP
  dynamic boost. PPD owns EPP/platform profile; Xe engines are discovered afresh.
- AC = native CPU/GPU ceilings + turbo enabled; preserve firmware limits.
  Battery = energy preferences, no arbitrary clock/power caps.
- Events = source/profile changes, bus ownership, resume; coalesce notifications,
  ignore successful self-generated profile changes, retry failures only.
  Unknown power source → no policy mutation. Partial failure → no cached success.
- Installer = Aeon `sdbootutil`, active Intel P-state now + next boot, system unit,
  replacement of the GNOME automatic profile selector. Reinstallation is idempotent.
- Gate = README Development + hardware `status` on physical AC and battery.
  Status exits nonzero on mismatch; tests use project-local fake sysfs trees.
