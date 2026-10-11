"""settings.yaml loading: paths, llm config (with .env support), sections."""
import os

import ruamel.yaml

from util import read_env_file


def load_config(path: str) -> dict:
    yaml = ruamel.yaml.YAML()
    with open(path, 'r', encoding='utf-8') as fh:
        raw = yaml.load(fh)
    base = os.path.dirname(os.path.abspath(path))

    def rp(p):
        p = str(p)
        return p if os.path.isabs(p) else os.path.normpath(os.path.join(base, p))

    llm = dict(raw.get('llm') or {})
    # api_key / base_url: the literal value "env" (or a missing value, the
    # default) means "read it from a .env file" instead of the config.
    envfile = {}
    for cand in (os.path.join(base, '.env'),
                 os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')):
        if os.path.isfile(cand):
            envfile = read_env_file(cand)
            break
    for key in ('api_key', 'base_url'):
        val = llm.get(key)
        if val is None or str(val).strip().lower() == 'env':
            val = envfile.get(key)
            if not val:
                raise SystemExit(f'settings: llm.{key} is "env" but {key}'
                                 f' was not found in .env (looked in: {base},'
                                 f' {os.path.dirname(os.path.abspath(__file__))})')
            llm[key] = val

    return {
        'source_dir': rp(raw['project']['source_dir']),
        'output_dir': rp(raw['project']['output_dir']),
        'data_dir': rp(raw['project']['data_dir']),
        'exclude': [str(x) for x in (raw['project'].get('exclude') or [])],
        'max_file_bytes': int(raw['project'].get('max_file_bytes', 26214400)),
        'llm': llm,
        'context': dict(raw.get('context') or {}),
        'documentation': dict(raw.get('documentation') or {}),
        'copy_meta': bool(raw['project'].get('copy_meta', False)),
        'concurrency': int(raw.get('concurrency') or 2),
        'tui': dict(raw.get('tui') or {}),
        'prompts': {k: rp(v) for k, v in (raw.get('prompts') or {}).items()},
    }
