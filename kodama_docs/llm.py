"""LLM client + prompt/validation loop (the only non-deterministic part).

The LLM only ever returns prose as a JSON object; ids, paths, links and
records are assembled elsewhere in plain Python.
"""
import json
import urllib.request

from kodama_docs.models import validate, extract_json_object, schema_text
from kodama_docs.util import log

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


NO_LLM_DESCRIPTION = 'No description generated (`--no-llm`)'
NO_LLM_SUMMARY = 'No summary generated (`--no-llm`)'

# Per-kind placeholder prose for --no-llm runs: schema-consistent stubs so the
# whole document still renders (description/summary slots), with the
# deterministic sections (parameters, references, call graph) coming from the
# static analysis + graph instead.
NO_LLM_PROSE = {
    'function': {'description': NO_LLM_DESCRIPTION},
    'variable': {'description': NO_LLM_DESCRIPTION},
    'chunk': {'summary': NO_LLM_DESCRIPTION},
    'summary': {'summary': NO_LLM_SUMMARY,
                'main_purpose': NO_LLM_SUMMARY,
                'role': NO_LLM_SUMMARY},
}


def generate(client: LLMClient, kind: str, base_prompt: str, user_ctx: str,
             max_invalid_retries: int = 2, no_llm: bool = False):
    """Ask the LLM for a JSON object of the given kind; validate; retry.

    With no_llm=True the model call is skipped entirely and a per-kind stub
    object is returned (no network, no retries).
    """
    if no_llm:
        return dict(NO_LLM_PROSE.get(kind, {'description': NO_LLM_DESCRIPTION}))
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
