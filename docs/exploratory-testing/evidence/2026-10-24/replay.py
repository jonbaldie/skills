#!/usr/bin/env python3
"""Drive installed public extractors with isolated, disclosed session fixtures."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = Path(__file__).resolve().parent
WORK = ROOT / '.fleet/exploratory-2026-10-24'
BASE_ENV = dict(os.environ)
for key in ('CODEX_HOME', 'CLAUDE_CONFIG_DIR', 'OPENCODE_DB', 'XDG_DATA_HOME',
            'PI_CODING_AGENT_DIR', 'PI_CODING_AGENT_SESSION_DIR'):
    BASE_ENV.pop(key, None)
BASE_ENV['PYTHONDONTWRITEBYTECODE'] = '1'


def run(name, command, home, cwd, **env):
    result = subprocess.run([str(c) for c in command], cwd=cwd,
                            env={**BASE_ENV, 'HOME': str(home), **env},
                            text=True, capture_output=True, timeout=120)
    log = f'cwd: {cwd}\nHOME: {home}\ncommand: {command!r}\nexit: {result.returncode}\n\nSTDOUT\n{result.stdout}\nSTDERR\n{result.stderr}'
    (EVIDENCE / f'{name}.log').write_text(log)
    print(f'{name}: exit {result.returncode}')
    return result


def jsonl(path, rows, mtime):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    os.utime(path, (mtime, mtime))


def pi_rows(sid, cwd, prompt):
    return [
        {'type': 'session', 'version': 3, 'id': sid, 'cwd': str(cwd), 'timestamp': '2026-10-24T00:00:00Z'},
        {'type': 'message', 'id': 'user1', 'parentId': None, 'message': {'role': 'user', 'content': prompt}},
        {'type': 'message', 'id': 'asst1', 'parentId': 'user1', 'message': {'role': 'assistant', 'content': [{'type': 'text', 'text': 'I will continue the requested change.'}], 'stopReason': 'stop'}},
    ]


def main():
    scratch = WORK / 'fixtures'
    if scratch.exists():
        raise SystemExit(f'Refusing existing fixture directory: {scratch}')
    scratch.mkdir(parents=True)
    observations = []
    for attempt in (1, 2):
        case = scratch / str(attempt)
        home = case / 'home'
        project = case / 'project'
        home.mkdir(parents=True)
        project.mkdir()
        install = run(f'install-router-{attempt}', [ROOT / 'install.sh', '--agent', 'pi', '--without-prereqs', '--skill', 'resume-from-agent'], home, project)
        assert install.returncode == 0
        router = project / '.agents/skills/resume-from-agent/scripts/extract-session.py'
        assert router.is_file() and not (project / '.agents/skills/resume-from-codex').exists()
        assert (project / '.pi/skills/resume-from-agent/scripts/extract-session.py').read_bytes() == router.read_bytes()
        sid = '11111111-1111-4111-8111-111111111111'
        codex = home / '.codex/sessions/2026/10/24' / f'rollout-2026-10-24T00-00-00-{sid}.jsonl'
        jsonl(codex, [
            {'type': 'session_meta', 'payload': {'id': sid, 'cwd': str(project), 'model_provider': 'openai'}},
            {'type': 'event_msg', 'payload': {'type': 'user_message', 'message': 'Implement invoice rounding and add boundary tests.'}},
            {'type': 'response_item', 'payload': {'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': 'Implement invoice rounding and add boundary tests.'}]}},
            {'type': 'event_msg', 'payload': {'type': 'agent_message', 'message': 'I will add rounding tests next.'}},
            {'type': 'response_item', 'payload': {'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': 'I will add rounding tests next.'}]}},
            {'type': 'event_msg', 'payload': {'type': 'turn_aborted', 'reason': 'interrupted'}},
        ], 1792800000)
        discovered = run(f'codex-discovery-alone-{attempt}', [sys.executable, router, '--cwd', project, 'codex'], home, project)
        explicit = run(f'codex-path-alone-{attempt}', [sys.executable, router, '--agent', 'codex', '--path', codex], home, project)
        install_sibling = run(f'install-codex-sibling-{attempt}', [ROOT / 'install.sh', '--agent', 'pi', '--without-prereqs', '--skill', 'resume-from-codex'], home, project)
        assert install_sibling.returncode == 0
        with_sibling = run(f'codex-discovery-sibling-{attempt}', [sys.executable, router, '--cwd', project, 'codex'], home, project)
        observations.append({'attempt': attempt, 'codex': {
            'discovered_goal': 'Implement invoice rounding' in discovered.stdout,
            'explicit_goal': 'Implement invoice rounding' in explicit.stdout,
            'with_sibling_goal': 'Implement invoice rounding' in with_sibling.stdout,
            'discovery_exit': discovered.returncode,
        }})

        # Two valid projects collide in Pi's lossy cwd directory encoding.
        left = case / 'apps/web-api'
        right = case / 'apps-web/api'
        left.mkdir(parents=True)
        right.mkdir(parents=True)
        encoded = lambda p: '--' + str(p).strip('/').replace('/', '-') + '--'
        assert encoded(left) == encoded(right)
        pi_root = home / '.pi/agent/sessions' / encoded(left)
        correct_id = '22222222-2222-4222-8222-222222222222'
        decoy_id = '33333333-3333-4333-8333-333333333333'
        correct = pi_root / f'2026-10-24T00-00-00_{correct_id}.jsonl'
        decoy = pi_root / f'2026-10-24T00-01-00_{decoy_id}.jsonl'
        jsonl(correct, pi_rows(correct_id, left, 'Fix the web-api invoice endpoint.'), 1792800000)
        jsonl(decoy, pi_rows(decoy_id, right, 'Migrate the OTHER project database.'), 1792800060)
        pi_script = ROOT / 'skills/resume-from-pi/scripts/extract-session.py'
        collision = run(f'pi-cwd-collision-{attempt}', [sys.executable, pi_script, '--cwd', left], home, left)
        router_collision = run(f'router-pi-cwd-collision-{attempt}', [sys.executable, router, '--cwd', left, 'pi'], home, left)
        listed = run(f'router-pi-list-{attempt}', [sys.executable, router, '--cwd', left, '--agent', 'pi', '--list'], home, left)
        pinned = run(f'pi-pinned-control-{attempt}', [sys.executable, pi_script, '--cwd', left, correct_id[:8]], home, left)
        # Exported paths and missing-id correction are supported user variations.
        exported = run(f'pi-explicit-path-{attempt}', [sys.executable, router, '--agent', 'pi', '--path', correct], home, left)
        unknown = run(f'pi-missing-id-{attempt}', [sys.executable, pi_script, '--cwd', left, 'deadbeef'], home, left)
        observations[-1]['pi'] = {
            'wrong_session_selected': decoy_id in collision.stdout,
            'router_wrong_session_selected': decoy_id in router_collision.stdout,
            'pinned_correct': correct_id in pinned.stdout,
            'explicit_correct_goal': 'Fix the web-api invoice endpoint.' in exported.stdout,
            'missing_id_exit': unknown.returncode,
            'list_exit': listed.returncode,
        }
        # Ordinary no-collision retry: remove only the fixture decoy.
        decoy.unlink()
        ordinary = run(f'pi-no-collision-control-{attempt}', [sys.executable, pi_script, '--cwd', left], home, left)
        observations[-1]['pi']['ordinary_correct'] = correct_id in ordinary.stdout
        missing_path = run(f'pi-missing-path-{attempt}', [sys.executable, router, '--agent', 'pi', '--path', case / 'missing.jsonl'], home, left)
        run(f'install-pi-sibling-{attempt}', [ROOT / 'install.sh', '--agent', 'pi', '--without-prereqs', '--skill', 'resume-from-pi'], home, project)
        exported_sibling = run(f'pi-explicit-path-sibling-{attempt}', [sys.executable, router, '--agent', 'pi', '--path', correct], home, left)
        observations[-1]['pi']['missing_path_exit'] = missing_path.returncode
        observations[-1]['pi']['explicit_uuid_preserved'] = f'session_id: {correct_id}\n' in exported.stdout
        observations[-1]['pi']['explicit_cwd_preserved'] = f'cwd: {left}\n' in exported.stdout
        observations[-1]['pi']['sibling_uuid_preserved'] = f'session_id: {correct_id}\n' in exported_sibling.stdout
        observations[-1]['pi']['sibling_cwd_preserved'] = f'cwd: {left}\n' in exported_sibling.stdout
    (EVIDENCE / 'observations.json').write_text(json.dumps(observations, indent=2) + '\n')
    print(json.dumps(observations, indent=2))


if __name__ == '__main__':
    main()
