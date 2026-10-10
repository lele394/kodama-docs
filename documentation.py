"""LLM prose generation (only non-deterministic part) + deterministic markdown.

The LLM only ever returns prose; ids, paths, links and records are assembled
here in plain Python, validated against models.SCHEMA and retried on failure.
"""
import hashlib
import json
import os
import urllib.request

from models import validate, extract_json_object, schema_text
from util import log, sanitize_id, trunc

USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
              'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36')


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, cfg: dict):
        self.base_url = cfg['base_url'].rstrip('/')
        self.api_key = cfg['api_key']
        self.model = cfg['model']
        self.max_retries = int(cfg.get('max_retries', 5))
        self.temperature = float(cfg.get('temperature', 0.1))
        self.max_tokens = int(cfg.get('max_tokens', 900))
        self.timeout = int(cfg.get('timeout', 300))

    def chat(self, system: str, user: str) -> str:
        body = json.dumps({
            'model': self.model,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
            'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': user},
            ],
        }).encode('utf-8')
        last_err = None
        for attempt in range(1, self.max_retries + 1):
            try:
                req = urllib.request.Request(
                    self.base_url + '/chat/completions',
                    data=body,
                    headers={
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + self.api_key,
                        'User-Agent': USER_AGENT,
                    },
                    method='POST')
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                return data['choices'][0]['message']['content']
            except Exception as e:  # noqa: BLE001 - retried uniformly
                last_err = e
                log(f'    llm attempt {attempt}/{self.max_retries} failed: {e}')
        raise LLMError('LLM call failed after retries: %r' % (last_err,))


def generate(client: LLMClient, kind: str, base_prompt: str, user_ctx: str,
             max_invalid_retries: int = 2):
    """Ask the LLM for a JSON object of the given kind; validate; retry."""
    system = (
        base_prompt.rstrip()
        + '\n\nReturn ONLY one JSON object, no markdown fences, matching this '
          'schema exactly:\n' + schema_text(kind)
        + '\n\nField values must be plain strings. Be concise and factual.'
    )
    errs_note = ''
    for i in range(max_invalid_retries + 1):
        user = user_ctx
        if errs_note:
            user += ('\n\nYour previous answer was INVALID: ' + errs_note
                     + '. Return corrected JSON only.')
        text = client.chat(system, user)
        obj = extract_json_object(text)
        if obj is None:
            errs_note = 'no JSON object found in response'
            continue
        errs = validate(kind, obj)
        if not errs:
            return obj
        errs_note = '; '.join(errs[:4])
    raise LLMError('invalid JSON after %d retries: %s'
                   % (max_invalid_retries, errs_note))


# ----------------------------------------------------------------- records

def record_path(data_dir: str, relpath: str, kind: str, name: str,
                line: int) -> str:
    sub = {'function': 'functions', 'variable': 'variables',
           'summary': 'summaries', 'chunk': 'chunks'}[kind]
    fhash = hashlib.md5(relpath.encode('utf-8')).hexdigest()[:10]
    fname = f'{kind}_{fhash}_{sanitize_id(name)}_{line}.json'
    return os.path.join(data_dir, sub, fname)


def save_record(data_dir: str, relpath: str, kind: str, name: str, line: int,
                prose: dict, fingerprint: str, symbol: dict):
    path = record_path(data_dir, relpath, kind, name, line)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rec = {
        'schema': 'doc_maker/record@1',
        'kind': kind,
        'file': relpath,
        'name': name,
        'line': line,
        'symbol': symbol,
        'prose': prose,
        'fingerprint': fingerprint,
    }
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=1)
    return path


def load_record(data_dir: str, relpath: str, kind: str, name: str,
                line: int, fingerprint: str):
    path = record_path(data_dir, relpath, kind, name, line)
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            rec = json.load(fh)
    except (ValueError, OSError):
        return None
    if rec.get('fingerprint') != fingerprint:
        return None
    return rec.get('prose')


def list_records(data_dir: str, kind: str):
    sub = {'function': 'functions', 'variable': 'variables',
           'summary': 'summaries', 'chunk': 'chunks'}[kind]
    d = os.path.join(data_dir, sub)
    out = {}
    if not os.path.isdir(d):
        return out
    for fname in sorted(os.listdir(d)):
        if not fname.endswith('.json'):
            continue
        try:
            with open(os.path.join(d, fname), 'r', encoding='utf-8') as fh:
                rec = json.load(fh)
            out[(rec.get('file'), rec.get('name'), rec.get('line'))] = rec
        except (ValueError, OSError):
            continue
    return out


# ------------------------------------------------------------- context text

def fn_chunks(body: str, max_lines: int, target_tokens: int = 0,
              chars_per_token: int = 4) -> list:
    """Split a function body into deterministic chunks.

    A chunk holds at most `max_lines` lines and (if target_tokens > 0) at
    most ~target_tokens input tokens, estimated with the configured
    chars-per-token ratio (a conservative upper bound for Lua). Breaks are
    preferred after top-level statements (indent <= the body's base
    indent) so chunks rarely start mid-block.
    """
    lines = body.splitlines()
    n = len(lines)
    cpt = max(1, int(chars_per_token or 4))
    budget = target_tokens * cpt if target_tokens else None
    if n == 0 or not any(l.strip() for l in lines):
        return []
    if n <= max_lines and (budget is None
                           or sum(len(l) + 1 for l in lines) <= budget):
        return [body]
    base = min((len(l) - len(l.lstrip()) for l in lines if l.strip()),
               default=0)
    chunks, i = [], 0
    while i < n:
        j, chars, last = i, 0, i
        while j < n and (j - i) < max_lines:
            if budget is not None and j > i \
                    and chars + len(lines[j]) + 1 > budget:
                break
            l = lines[j]
            chars += len(l) + 1
            if j > i and (len(l) - len(l.lstrip())) <= base:
                last = j + 1
            j += 1
        end = j
        if end <= i:                      # one line over budget: force progress
            end = i + 1
        elif end < n and last > i:        # split after the last top-level stmt
            end = last
        chunks.append('\n'.join(lines[i:end]))
        i = end
    return chunks


def fn_context_text(fn: dict, calls_in, calls_out, ctx_cfg: dict,
                    body_note: str = None) -> str:
    max_list = int(ctx_cfg.get('max_symbols_per_list', 25))
    max_lines = int(ctx_cfg.get('max_source_lines', 300))
    body = fn.get('body', '')
    blines = body.splitlines()
    if len(blines) > max_lines:
        body = '\n'.join(blines[:max_lines]) + f'\n-- ... ({len(blines) - max_lines} more lines)'
    parts = [
        f"Symbol: {fn.get('qualified') or fn['name']} (line {fn['line']}"
        + (f"-{fn['end_line']}" if fn.get('end_line', 0) > fn['line'] else '') + ')',
        f"File: {fn['relpath']}",
        'Parameters: ' + (', '.join(fn.get('params') or []) or '(none)')
        + (' + varargs' if fn.get('vararg') else ''),
    ]
    if calls_in:
        parts.append('Called by: ' + ', '.join(dict.fromkeys(calls_in))[:500])
    if calls_out:
        parts.append('Calls: ' + ', '.join(dict.fromkeys(calls_out))[:500])
    if body_note is not None:
        parts.append(body_note)
    else:
        parts.append('Source (Lua):\n```lua\n' + body + '\n```')
    return '\n'.join(parts)


def var_context_text(var: dict, ctx_cfg: dict) -> str:
    parts = [
        f"Symbol: {var['name']} (line {var['line']})",
        f"File: {var['relpath']}",
        f"Initialization: {var.get('init', 'unknown')}",
    ]
    if var.get('init') == 'string' and var.get('value'):
        parts.append('Value: ' + trunc(str(var['value']), 200))
    return '\n'.join(parts)


def summary_context_text(finfo: dict, ctx_cfg: dict) -> str:
    max_list = int(ctx_cfg.get('max_symbols_per_list', 25))
    fns = finfo.get('functions') or []
    vars_ = finfo.get('file_vars') or []
    fns_txt = ', '.join(
        (f.get('qualified') or f['name']) for f in fns[:max_list])
    vars_txt = ', '.join(v['name'] for v in vars_[:max_list])
    heads = [f for f in fns[:6] if (f.get('body') or '').strip()]
    head_txt = ''
    for h in heads:
        head_txt += f"\n--- {h.get('qualified') or h['name']} ---\n"
        head_txt += trunc(h.get('body', ''), 600)
    return '\n'.join([
        f"File: {finfo['relpath']} ({finfo.get('lines', '?')} lines)",
        f"Function count: {len(fns)}" + (f" (showing {max_list})" if len(fns) > max_list else ''),
        'Functions: ' + (fns_txt or '(none)'),
        'File-level variables: ' + (vars_txt or '(none)'),
        'Representative code:' + (head_txt or ' (none)'),
    ])


# ------------------------------------------------------------- markdown out

def md_escape(s: str) -> str:
    return str(s).replace('|', '\\|')


def _fn_anchor(fn: dict) -> str:
    return f"fn-{sanitize_id(fn['name'])}-{fn['line']}"


def render_file_md(finfo: dict, fn_records, var_records, summary,
                   output_root: str) -> str:
    rel = finfo['relpath']
    lines = [f'# {rel}', '']
    if summary:
        lines += ['## Summary', '', summary.get('summary', ''),
                  f"**Main purpose:** {summary.get('main_purpose', '')}",
                  f"**Role in project:** {summary.get('role', '')}", '']
    else:
        lines += ['_No summary generated._', '']

    funcs = finfo.get('functions') or []
    if funcs:
        lines += ['## Functions', '']
        lines.append('| Function | Line | Parameters | Description |')
        lines.append('| --- | --- | --- | --- |')
        for fn in funcs:
            rec = fn_records.get((rel, fn['name'], fn['line']))
            desc = ''
            if rec and rec.get('prose'):
                desc = md_escape(trunc(rec['prose'].get('description', ''), 140))
            params = ', '.join(fn.get('params') or [])
            lines.append(f"| [{fn.get('qualified') or fn['name']}]#{_fn_anchor(fn)} "
                         f"| {fn['line']} | {md_escape(params)} | {desc} |")
        lines.append('')
        for fn in funcs:
            rec = fn_records.get((rel, fn['name'], fn['line']))
            lines.append(f"### {fn.get('qualified') or fn['name']}"
                         f" <a id=\"{_fn_anchor(fn)}\"></a>")
            lines.append('')
            lines.append(f"*{rel}:{fn['line']}"
                         + (f"-{fn['end_line']}" if fn.get('end_line', 0) > fn['line'] else '')
                         + '*')
            lines.append('')
            if rec and rec.get('prose'):
                p = rec['prose']
                lines.append(md_escape(p.get('description', '')))
                lines.append('')
                if p.get('arguments'):
                    lines.append('**Parameters**')
                    lines.append('')
                    lines.append('| Name | Description |')
                    lines.append('| --- | --- |')
                    for a in p['arguments']:
                        lines.append(f"| `{a.get('name', '')}` "
                                     f"| {md_escape(a.get('description', ''))} |")
                    lines.append('')
                if p.get('outputs'):
                    lines.append('**Outputs**')
                    lines.append('')
                    lines.append('| Name | Description |')
                    lines.append('| --- | --- |')
                    for o in p['outputs']:
                        nm = o.get('name') or 'return value'
                        lines.append(f"| `{md_escape(nm)}` "
                                     f"| {md_escape(o.get('description', ''))} |")
                    lines.append('')
                if p.get('side_effects'):
                    lines.append('**Side effects**')
                    lines.append('')
                    for s in p['side_effects']:
                        lines.append(f'- {md_escape(s)}')
                    lines.append('')
                if p.get('references'):
                    lines.append('**References**')
                    lines.append('')
                    for r in p['references']:
                        lines.append(f'- {md_escape(r)}')
                    lines.append('')
                if p.get('uncertainties'):
                    lines.append('**Uncertainties**')
                    lines.append('')
                    for u in p['uncertainties']:
                        lines.append(f'- {md_escape(u)}')
                    lines.append('')
            else:
                lines.append('_No description generated._')
                lines.append('')
            body = (fn.get('body') or '').strip()
            if body:
                lines.append('```lua')
                lines.append(body)
                lines.append('```')
                lines.append('')

    vars_ = finfo.get('file_vars') or []
    if vars_:
        lines += ['## File-level variables', '']
        lines.append('| Variable | Line | Init | Description |')
        lines.append('| --- | --- | --- | --- |')
        for v in vars_:
            rec = var_records.get((rel, v['name'], v['line']))
            desc = ''
            if rec and rec.get('prose'):
                desc = md_escape(trunc(rec['prose'].get('description', ''), 140))
            lines.append(f"| `{v['name']}` | {v['line']} "
                         f"| {md_escape(v.get('init', ''))} | {desc} |")
        lines.append('')

    lines.append('---')
    lines.append('_Generated by doc_maker. Prose produced by an LLM; '
                 'structure and links generated deterministically._')
    lines.append('')
    return '\n'.join(lines)


def render_index(finfos, output_root: str) -> str:
    lines = ['# Documentation index', '',
             f'{len(finfos)} files documented.', '',
             '| File | Lines | Functions | Variables |',
             '| --- | --- | --- | --- |']
    for finfo in finfos:
        rel = finfo['relpath']
        mdname = rel.rsplit('/', 1)[-1].rsplit('.', 1)[0]
        lines.append(
            f"| [{rel}](files/{rel}.md) | {finfo.get('lines', '?')} "
            f"| {len(finfo.get('functions') or [])} "
            f"| {len(finfo.get('file_vars') or [])} |")
    lines.append('')
    lines.append('---')
    lines.append('_Generated by doc_maker._')
    lines.append('')
    return '\n'.join(lines)


def write_md(text: str, output_root: str, rel: str):
    path = os.path.join(output_root, 'files', rel + '.md')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(text)
    return path
