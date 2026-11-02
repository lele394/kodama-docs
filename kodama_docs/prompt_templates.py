"""Deterministic prompt-template fields.

Prompt files may use ``{key}`` placeholders. Rendering is a single-pass
substitution of *known* keys only, so JSON examples or other braces in a
prompt are left alone.

Keys:
    {language}            human label: Python, Lua, C, C++, CUDA
    {language_family}     backend family: python, lua, c-family
    {dialect}             c / cpp / cuda (empty otherwise)
    {file}                source relpath
    {symbol}              qualified symbol name (file path for summaries)
    {name}                unqualified symbol name
    {kind}                function / function chunk / variable / file summary
    {line}                symbol start line
    {line_end}            symbol end line
    {params}              comma-separated parameter names
    {fence}               code-fence language for this file
    {developer_comment}   glued developer comment (empty if none)
"""
import os
import re

from kodama_docs.util import fence_lang

_FIELD_RE = re.compile(r'\{([a-z_]+)\}')
_LANG_NAMES = {'python': 'Python', 'lua': 'Lua'}
_EXT_LANG = {
    '.py': 'Python', '.pyi': 'Python', '.lua': 'Lua',
    '.c': 'C', '.h': 'C/C++', '.cc': 'C++', '.cpp': 'C++',
    '.cxx': 'C++', '.hh': 'C++', '.hpp': 'C++', '.hxx': 'C++',
    '.cu': 'CUDA', '.cuh': 'CUDA',
}


def language_name(f: dict) -> str:
    """Human-readable language for a file record."""
    lang = str(f.get('lang') or '').strip()
    if lang == 'c-family':
        dialect = str(f.get('dialect') or '').lower()
        return {'c': 'C', 'cpp': 'C++', 'cuda': 'CUDA'}.get(
            dialect, 'C/C++')
    if lang:
        return _LANG_NAMES.get(lang, lang.replace('-', ' ').title())
    ext = os.path.splitext(str(f.get('relpath') or ''))[1].lower()
    return _EXT_LANG.get(ext, 'source')


def prompt_fields(f: dict, sym: dict | None = None, kind: str = '') -> dict:
    """Values available to a prompt template for one LLM task."""
    sym = sym or {}
    rel = str(f.get('relpath') or '')
    name = str(sym.get('name') or os.path.basename(rel) or '')
    qualified = str(sym.get('qualified') or name or rel)
    if kind == 'file summary':
        name = os.path.basename(rel)
        qualified = rel
    return {
        'language': language_name(f),
        'language_family': str(f.get('lang') or ''),
        'dialect': str(f.get('dialect') or ''),
        'file': rel,
        'symbol': qualified,
        'name': name,
        'kind': kind,
        'line': str(sym.get('line') or ''),
        'line_end': str(sym.get('end_line') or sym.get('line') or ''),
        'params': ', '.join(str(p) for p in (sym.get('params') or [])),
        'fence': fence_lang(rel),
        'developer_comment': str(sym.get('developer_comment') or ''),
    }


def render_prompt(template: str, fields: dict) -> str:
    """Replace known ``{key}`` placeholders in one pass.

    Unknown placeholders are left verbatim — they may be intentional (for
    example a JSON example in a custom prompt).
    """
    text = str(template or '')
    return _FIELD_RE.sub(
        lambda m: str(fields[m.group(1)])
        if m.group(1) in fields else m.group(0),
        text)
