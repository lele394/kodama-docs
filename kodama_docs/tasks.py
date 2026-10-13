"""Per-task record fingerprints — the single shared definition (P0-4).

A cached LLM record may only be reused if its stored fingerprint equals the
one computed here. A fingerprint covers everything that can change the
result:

  * the source content of the symbol (body / init / file structure);
  * the analysis configuration: model, base URL, prompt text, and the
    context/generation settings that shape the prompt;
  * for functions, the current call relationships (callers and callees),
    so a record is regenerated when the graph around a symbol changes.

Both consumers — the LLM phase (save/load) and the "Skipped (cached)"
report line — must use these functions, so the definition lives here and
not in either consumer.
"""
import hashlib


def task_fp(*parts) -> str:
    """sha256 over a deterministic serialization of the parts."""
    h = hashlib.sha256()
    for p in parts:
        h.update(repr(p).encode('utf-8'))
        h.update(b'\x00')
    return h.hexdigest()


def settings_fp(cfg: dict, kind: str) -> str:
    """Fingerprint of the generation settings for one task kind:
    model, base URL, prompt text and the context/generation knobs."""
    llm = cfg.get('llm') or {}
    prompt_path = (cfg.get('prompts') or {}).get(kind)
    try:
        with open(prompt_path, 'r', encoding='utf-8') as fh:
            prompt = fh.read()
    except (OSError, TypeError):
        prompt = ''
    doc = cfg.get('documentation') or {}
    ctx = sorted((cfg.get('context') or {}).items(),
                 key=lambda kv: str(kv[0]))
    return task_fp('settings', kind,
                   llm.get('model') or '',
                   llm.get('base_url') or '',
                   prompt,
                   ctx,
                   doc.get('max_function_lines'),
                   doc.get('max_chunk_lines'),
                   doc.get('chunk_target_tokens'),
                   doc.get('chars_per_token'))


def function_fp(rel, fn, calls_in, calls_out, settings) -> str:
    return task_fp('function', rel,
                   fn.get('name'), fn.get('line'),
                   fn.get('body') or '',
                   sorted(fn.get('params') or []),
                   bool(fn.get('vararg')),
                   settings,
                   sorted(calls_in), sorted(calls_out))


def variable_fp(rel, v, settings) -> str:
    return task_fp('variable', rel,
                   v.get('name'), v.get('line'),
                   v.get('init'), v.get('module'), v.get('value'),
                   settings)


def summary_fp(rel, f, settings) -> str:
    fns = sorted((fn.get('qualified') or fn.get('name'), fn.get('line'))
                 for fn in (f.get('functions') or []))
    vars_ = sorted((v.get('name'), v.get('line'))
                   for v in (f.get('file_vars') or []))
    return task_fp('summary', rel, f.get('lines'), fns, vars_, settings)


def chunk_fp(rel, chunk_name, line, text, settings) -> str:
    return task_fp('chunk', rel, chunk_name, line, text, settings)
