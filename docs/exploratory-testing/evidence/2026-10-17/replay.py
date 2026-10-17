#!/usr/bin/env python3
"""Drive supported install/sync/copy commands; use only isolated project data."""
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
WORK = ROOT / '.fleet/exploratory-2026-10-17'
EVIDENCE = Path(__file__).resolve().parent
ENV = dict(os.environ, HOME=str(WORK / 'home'),
           JONBALDIE_SKILLS_REPO=str(ROOT),
           MATTPOCOCK_SKILLS_REPO=str(WORK / 'sources/mattpocock'))
SCRIPTS = ROOT / 'skills/sync-jonbaldie-skills/scripts'
if (WORK / 'projects').exists():
    raise SystemExit(f'Remove only the isolated {WORK / "projects"} before replaying.')
(WORK / 'home').mkdir(parents=True, exist_ok=True)


def run(label, args, cwd=ROOT, env=None):
    with (EVIDENCE / (label + '.log')).open('w') as log:
        log.write(f'cwd: {cwd}\nargv: {args!r}\n')
        log.flush()
        try:
            result = subprocess.run([str(a) for a in args], cwd=cwd,
                                    env=env or ENV, stdin=subprocess.DEVNULL,
                                    stdout=log, stderr=subprocess.STDOUT, timeout=90)
            log.write(f'EXIT: {result.returncode}\n')
        except subprocess.TimeoutExpired:
            log.write('TIMEOUT: 90 seconds\n')
            raise


def note(label, text):
    with (EVIDENCE / (label + '.log')).open('a') as log:
        log.write(text + '\n')


for n in (1, 2):
    project = WORK / 'projects' / f'install-{n}'
    project.mkdir(parents=True, exist_ok=True)
    run(f'install-{n}', [ROOT / 'install.sh', '--agent', 'pi', '--without-prereqs',
                        '--skill', 'options', '--skill', 'mutation-testing'], project)
    note(f'install-{n}', f"pi options resolves: {(project / '.pi/skills/options').resolve()}\n"
         f"installed: {sorted(p.name for p in (project / '.agents/skills').iterdir())}")
    run(f'install-mixed-filter-{n}', [ROOT / 'install.sh', '--agent', 'pi',
        '--without-prereqs', '--skill', 'options', '--skill', 'not-a-real-skill'], project)

project = WORK / 'projects' / 'sync'
(project / '.agents/skills/unrelated').mkdir(parents=True, exist_ok=True)
(project / '.agents/skills/unrelated/sentinel').write_text('keep me\n')
run('sync-first', [SCRIPTS / 'sync-skills.sh', project])
(project / '.agents/skills/options/stale').write_text('remove me\n')
run('sync-update', [SCRIPTS / 'sync-skills.sh', project])
note('sync-update', f"stale exists: {(project / '.agents/skills/options/stale').exists()}\n"
     f"unrelated: {(project / '.agents/skills/unrelated/sentinel').read_text()!r}")
before = (project / '.agents/sync-jonbaldie-skills.manifest').read_bytes()
failed_env = dict(ENV, MATTPOCOCK_SKILLS_REPO=str(WORK / 'missing-repository'))
run('sync-fetch-failure', [SCRIPTS / 'sync-skills.sh', project], env=failed_env)
note('sync-fetch-failure', f"manifest unchanged: {before == (project / '.agents/sync-jonbaldie-skills.manifest').read_bytes()}")
run('copy-first', [SCRIPTS / 'copy-to-skill-dirs.sh', project, '--agent', 'claude-code', 'custom skills'])
run('copy-repeat', [SCRIPTS / 'copy-to-skill-dirs.sh', project, '--agent', 'claude-code', 'custom skills'])
run('copy-invalid-agent', [SCRIPTS / 'copy-to-skill-dirs.sh', project, 'should-not-exist', '--agent', 'invalid'])
note('copy-invalid-agent', f"earlier destination exists: {(project / 'should-not-exist').exists()}")
for name in ('options', 'sync-jonbaldie-skills'):
    source = project / '.agents/skills' / name / 'SKILL.md'
    target = project / '.claude/skills' / name / 'SKILL.md'
    note('copy-repeat', f'{name} bytes match: {source.read_bytes() == target.read_bytes()}')

# Minimal installed-project fixture: ordinary name and manifest format emitted by sync.
# Destination is an existing skill directory, a plausible mistaken custom path.
for n in (1, 2):
    project = WORK / 'projects' / f'copy-overlap-{n}'
    canonical = project / '.agents/skills/options'
    canonical.mkdir(parents=True, exist_ok=True)
    (canonical / 'SKILL.md').write_bytes((ROOT / 'skills/options/SKILL.md').read_bytes())
    (project / '.agents/sync-jonbaldie-skills.manifest').write_text('options\n')
    run(f'copy-overlap-{n}', [SCRIPTS / 'copy-to-skill-dirs.sh', project, '.agents/skills/options'])
    files = list(canonical.rglob('SKILL.md'))
    note(f'copy-overlap-{n}', f'SKILL.md count after copy: {len(files)}\n'
         f'original exists: {(canonical / "SKILL.md").exists()}')

for n in (1, 2):
    project = WORK / 'projects' / f'copy-root-bypass-{n}'
    canonical = project / '.agents/skills/options'
    canonical.mkdir(parents=True, exist_ok=True)
    (canonical / 'SKILL.md').write_bytes((ROOT / 'skills/options/SKILL.md').read_bytes())
    (project / '.agents/sync-jonbaldie-skills.manifest').write_text('options\n')
    (project / 'options').mkdir(exist_ok=True)
    (project / 'options/user-work.txt').write_text('unrelated user work\n')
    run(f'copy-root-direct-{n}', [SCRIPTS / 'copy-to-skill-dirs.sh', project, '.'])
    note(f'copy-root-direct-{n}', f'user work exists: {(project / "options/user-work.txt").exists()}')
    run(f'copy-root-bypass-{n}', [SCRIPTS / 'copy-to-skill-dirs.sh', project, 'new/..'])
    note(f'copy-root-bypass-{n}', f'user work exists: {(project / "options/user-work.txt").exists()}\n'
         f'root SKILL.md exists: {(project / "options/SKILL.md").exists()}')
