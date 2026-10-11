"""Output schemas (JSON-Schema subset) + deterministic validator.

The same schemas are embedded verbatim in LLM prompts, so the model and the
validator can never disagree about the expected shape.
"""
import json

SCHEMA = {
    'function': {
        'type': 'object',
        'required': ['description'],
        'additionalProperties': False,
        'properties': {
            'description': {'type': 'string', 'minLength': 8},
            'arguments': {'type': 'array', 'maxItems': 64, 'items': {
                'type': 'object', 'required': ['name'], 'additionalProperties': False,
                'properties': {
                    'name': {'type': 'string', 'minLength': 1},
                    'description': {'type': 'string'},
                }}},
            'outputs': {'type': 'array', 'maxItems': 32, 'items': {
                'type': 'object', 'required': ['description'], 'additionalProperties': False,
                'properties': {
                    'name': {'type': ['string', 'null']},
                    'description': {'type': 'string', 'minLength': 3},
                }}},
            'side_effects': {'type': 'array', 'maxItems': 32, 'items': {'type': 'string'}},
            'references': {'type': 'array', 'maxItems': 64, 'items': {'type': 'string'}},
            'uncertainties': {'type': 'array', 'maxItems': 32, 'items': {'type': 'string'}},
        },
    },
    'chunk': {
        'type': 'object',
        'required': ['summary'],
        'additionalProperties': False,
        'properties': {
            'summary': {'type': 'string', 'minLength': 12},
        },
    },
    'variable': {
        'type': 'object',
        'required': ['description'],
        'additionalProperties': False,
        'properties': {
            'description': {'type': 'string', 'minLength': 8},
            'notes': {'type': 'array', 'maxItems': 16, 'items': {'type': 'string'}},
        },
    },
    'summary': {
        'type': 'object',
        'required': ['summary', 'main_purpose', 'role'],
        'additionalProperties': False,
        'properties': {
            'summary': {'type': 'string', 'minLength': 16},
            'main_purpose': {'type': 'string', 'minLength': 8},
            'role': {'type': 'string', 'minLength': 8},
        },
    },
}


def schema_text(name: str) -> str:
    return json.dumps(SCHEMA[name], indent=2)


def validate(name: str, obj) -> list:
    """Return a list of human-readable errors (empty list if valid)."""
    errs = []
    _check(SCHEMA[name], obj, '$', errs)
    return errs


def _type_ok(t, v) -> bool:
    if t == 'string':
        return isinstance(v, str)
    if t == 'number':
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if t == 'integer':
        return isinstance(v, int) and not isinstance(v, bool)
    if t == 'boolean':
        return isinstance(v, bool)
    if t == 'array':
        return isinstance(v, list)
    if t == 'object':
        return isinstance(v, dict)
    if t == 'null':
        return v is None
    return True


def _check(spec, v, path, errs):
    t = spec.get('type')
    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(_type_ok(x, v) for x in types):
            errs.append(f'{path}: expected type {"/".join(types)}, got {type(v).__name__}')
            return
    if isinstance(v, str) and 'minLength' in spec and len(v.strip()) < spec['minLength']:
        errs.append(f'{path}: string shorter than {spec["minLength"]} chars')
    if isinstance(v, list):
        if 'maxItems' in spec and len(v) > spec['maxItems']:
            errs.append(f'{path}: more than {spec["maxItems"]} items')
        if 'items' in spec:
            for i, item in enumerate(v):
                _check(spec['items'], item, f'{path}[{i}]', errs)
    if isinstance(v, dict):
        for req in spec.get('required', []):
            if req not in v:
                errs.append(f'{path}: missing required key "{req}"')
        props = spec.get('properties', {})
        if spec.get('additionalProperties') is False:
            for k in v:
                if k not in props:
                    errs.append(f'{path}: unknown key "{k}"')
        for k, sub in props.items():
            if k in v:
                _check(sub, v[k], f'{path}.{k}', errs)


def extract_json_object(text: str):
    """Deterministically pull the first balanced JSON object out of a text.

    String literals are respected; returns the parsed object or None.
    """
    if not text:
        return None
    start = text.find('{')
    while start != -1:
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == '\\':
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except (ValueError, TypeError):
                        break
        start = text.find('{', start + 1)
    return None
