"""Prompt context builders: deterministic chunking + per-kind context text."""

from docmaker.util import fence_lang, trunc


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
        lang = fence_lang(fn['relpath'])
        parts.append(f'Source ({lang}):\n```{lang}\n' + body + '\n```')
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
