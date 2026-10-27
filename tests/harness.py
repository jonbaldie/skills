"""Shared fixtures for tests of standalone skill scripts."""

import importlib.util
import io
import os
import sys
from contextlib import contextmanager, redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def load_skill_script(skill_name, script_name):
    path = ROOT / "skills" / skill_name / "scripts" / script_name
    name = f"skill_{skill_name.replace('-', '_')}_{path.stem.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@contextmanager
def isolated_env(**overrides):
    previous = {key: os.environ.get(key) for key in overrides}
    try:
        for key, value in overrides.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def make_workspace_symlink_pair(root):
    physical = root / "workspace" / "project"
    physical.mkdir(parents=True)
    link = root / "workspace" / "project-link"
    link.symlink_to(physical, target_is_directory=True)
    return physical, link


def run_cli(main_fn, args):
    output = io.StringIO()
    with redirect_stdout(output):
        main_fn(args)
    return output.getvalue()
