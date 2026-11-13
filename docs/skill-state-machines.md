# Skill state machines

The transition tables in each skill control its next action. They name the
state, the event and evidence required to leave it, and the next state or
action. A waiting, blocked, incomplete, or unverified result is distinct from
completion. These are agent instructions, not a runtime orchestration engine.

This inventory covers 27 skills, including the in-progress Tutor and deprecated
ship-spec. The installer continues to exclude both draft and deprecated skills.

| Skills | State carried between actions | Main recovery guard |
| --- | --- | --- |
| [bmf](../skills/bmf/SKILL.md) | Source, contract, reference version, derivation ledger and checks | Changed premises invalidate dependent work. A Fit report is an alternate terminal result. |
| [tutor](../skills/in-progress/tutor/SKILL.md) | Mission, chosen beat, pending question and used repair attempt | Restore the checkpoint; understanding does not grant permission to continue. |
| [to-summary](../skills/to-summary/SKILL.md) | Source snapshot, ordered chunk lineage, hashes and attempts | Rebuild invalid outputs; repeated failure or nonprogress ends as incomplete. |
| [worked-example](../skills/worked-example/SKILL.md) | Current mechanism and learner response | Trace the unclear decision again or confirm demonstrated understanding. |
| [exploratory-testing](../skills/exploratory-testing/SKILL.md) | Candidate evidence and owned resources | Confirm by replay; verify cleanup before completion. |
| [finding-bugs](../skills/finding-bugs/SKILL.md) | Search feedback, replay state and candidate disposition | Verify resets and stable reproduction; keep deferred or unstable work visible. |
| [mutation-testing](../skills/mutation-testing/SKILL.md) | Exact baseline, one active mutant and check configuration | Restore and reverify before classifying or proceeding. |
| [perffuzz](../skills/perffuzz/SKILL.md) | Campaign configuration, per-location maxima and witnesses | Reset incompatible evidence; replay and reduce a reproducible impact predicate. |
| [hill-climbing](../skills/hill-climbing/SKILL.md) | Baseline, active experiment, retained change and field evidence | Restore rejected changes; field confirmation requires field evidence. |
| [scale-test-impact-analysis](../skills/scale-test-impact-analysis/SKILL.md) | Workflow, durable result receipt, selector freshness and rollout | Acknowledgement, history application and promotion have separate guards. |
| [resume-from-agent](../skills/resume-from-agent/SKILL.md), [Claude](../skills/resume-from-claude/SKILL.md), [Codex](../skills/resume-from-codex/SKILL.md), [OpenCode](../skills/resume-from-opencode/SKILL.md), [Pi](../skills/resume-from-pi/SKILL.md) | Selected session, actual workspace and grounded next action | Resolve and ground again after changed evidence; a transcript does not grant new authority. |
| [resume-from-pr](../skills/resume-from-pr/SKILL.md) | PR identity, fetched head, host-data gaps and workspace | Isolate unrelated dirty work and refresh changed heads. |
| [ship-pr](../skills/ship-pr/SKILL.md) | Exact PR, checked head, queue status and merge result | A changed head invalidates checks; queue entry is not a merge. |
| [land-the-plane](../skills/land-the-plane/SKILL.md) | Assigned work, verified candidate and integrated tree | Changed work or remote tip requires verification again; failed integrated checks prevent success. |
| [promote-fork-pr-upstream](../skills/promote-fork-pr-upstream/SKILL.md) | Route, intended patches, captured fork SHA and candidate | A failed lease requires a new audit. |
| [ship-spec](../skills/deprecated/ship-spec/SKILL.md) | Parent, dependency-ready child and verified remote target | Remote integration gates selection of the next child. |
| [sync-jonbaldie-skills](../skills/sync-jonbaldie-skills/SKILL.md) | Source commits, managed names and selected destinations | Validate before copying; preserve failed replacements and report partial application. |

Six skills remain procedures or classifiers rather than acquiring artificial
lifecycle states. They are [deintrovert-tests](../skills/deintrovert-tests/SKILL.md),
[finding-seams](../skills/finding-seams/SKILL.md), [options](../skills/options/SKILL.md),
[seeking-performance](../skills/seeking-performance/SKILL.md),
[user-journeys](../skills/user-journeys/SKILL.md), and
[walk-the-spec](../skills/walk-the-spec/SKILL.md). Evidence labels classify a
result; labels alone do not define events that move it between states.
