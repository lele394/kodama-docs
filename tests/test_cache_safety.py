"""Cache/output safety tests (no LLM, no network).

Run:  .venv/bin/python tests/test_cache_safety.py

Guards three failure modes found in review:
  * --no-llm stubs must never overwrite real cached prose;
  * the render phase must not use records whose fingerprint is stale;
  * resetting the output dir must remove stale generated files but keep
    .doc_cache, and must refuse a directory that contains the source tree.
"""
import json
import os
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import backends  # noqa: E402
from kodama_docs import graph as gmod  # noqa: E402
from kodama_docs import outputs, records  # noqa: E402
from kodama_docs.tasks import function_fp, settings_fp  # noqa: E402
from main import _valid_records  # noqa: E402


def mk(src, rel):
    r = backends.extract(src, rel)
    r['relpath'] = rel
    r['lines'] = len(src.splitlines())
    r['size'] = len(src.encode())
    r['status'] = 'ok'
    return r


def cfg_for(tmp, generate=True):
    return {
        'data_dir': os.path.join(tmp, 'data'),
        'output_dir': os.path.join(tmp, 'out'),
        'source_dir': os.path.join(tmp, 'src'),
        'documentation': {
            'generate_function_docs': generate,
            'generate_variable_docs': generate,
            'generate_file_summaries': generate,
        },
        'context': {},
        'prompts': {},
        'llm': {},
    }


def test_no_llm_stub_never_overwrites_real_prose(tmp):
    cfg = cfg_for(tmp)
    os.makedirs(cfg['data_dir'], exist_ok=True)
    records.save_record(cfg['data_dir'], 'a.py', 'function', 'f', 1,
                        {'description': 'REAL PROSE'}, 'fp-real', {}, False)
    records.save_record(cfg['data_dir'], 'a.py', 'function', 'f', 1,
                        {'description': 'No description generated'},
                        'fp-new', {}, True)
    path = records.record_path(cfg['data_dir'], 'a.py', 'function', 'f', 1)
    with open(path, 'r', encoding='utf-8') as fh:
        rec = json.load(fh)
    assert rec['prose']['description'] == 'REAL PROSE', rec
    assert not rec.get('stubbed'), rec
    print('ok   test_no_llm_stub_never_overwrites_real_prose')


def test_render_filters_stale_and_disabled_records(tmp):
    cfg = cfg_for(tmp)
    os.makedirs(cfg['data_dir'], exist_ok=True)
    f = mk('def f():\n    return 1\n', 'a.py')
    g, _diag = gmod.build_graph([f])
    nid = gmod.node_id_fn('a.py', 'f', 1)
    ins, outs = gmod.graph_neighbor_names(g, nid)
    fp = function_fp('a.py', f['functions'][0], ins, outs,
                     settings_fp(cfg, 'function'))
    records.save_record(cfg['data_dir'], 'a.py', 'function', 'f', 1,
                        {'description': 'current'}, fp, {}, False)
    fn_recs, _var, _sum = _valid_records(cfg, [f], g)
    assert ('a.py', 'f', 1) in fn_recs, fn_recs

    # stale fingerprint -> not rendered
    path = records.record_path(cfg['data_dir'], 'a.py', 'function', 'f', 1)
    with open(path, 'r', encoding='utf-8') as fh:
        rec = json.load(fh)
    rec['fingerprint'] = 'stale'
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(rec, fh)
    fn_recs, _var, _sum = _valid_records(cfg, [f], g)
    assert not fn_recs, fn_recs

    # a disabled generator must not surface old prose either
    rec['fingerprint'] = fp
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(rec, fh)
    cfg_off = cfg_for(tmp, generate=False)
    fn_recs, _var, _sum = _valid_records(cfg_off, [f], g)
    assert not fn_recs, fn_recs
    print('ok   test_render_filters_stale_and_disabled_records')


def test_reset_output_keeps_doc_cache_and_prunes(tmp):
    cfg = cfg_for(tmp)
    os.makedirs(os.path.join(cfg['output_dir'], 'files'), exist_ok=True)
    os.makedirs(os.path.join(cfg['output_dir'], 'manual'), exist_ok=True)
    with open(os.path.join(cfg['output_dir'], 'index.md'), 'w') as fh:
        fh.write('stale')
    with open(os.path.join(cfg['output_dir'], '.doc_cache'), 'w') as fh:
        fh.write('{}')
    outputs.reset_output(cfg)
    assert os.path.isfile(os.path.join(cfg['output_dir'], '.doc_cache'))
    assert not os.path.exists(os.path.join(cfg['output_dir'], 'index.md'))
    assert not os.path.exists(os.path.join(cfg['output_dir'], 'files'))
    assert not os.path.exists(os.path.join(cfg['output_dir'], 'manual'))
    print('ok   test_reset_output_keeps_doc_cache_and_prunes')


def test_config_without_credentials_for_non_llm_modes(tmp):
    import kodama_docs.config as config
    path = os.path.join(tmp, 'settings.yaml')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write('project:\n'
                 '  source_dir: src\n'
                 '  output_dir: out\n'
                 '  data_dir: data\n'
                 'llm:\n'
                 '  base_url: env\n'
                 '  api_key: env\n'
                 '  model: dummy\n')
    old = config.read_env_file
    config.read_env_file = lambda _p: {}
    try:
        cfg = config.load_config(path, require_llm=False)
        assert cfg['llm']['api_key'] == '', cfg['llm']
        assert cfg['llm']['base_url'] == '', cfg['llm']
        try:
            config.load_config(path, require_llm=True)
        except SystemExit:
            pass
        else:
            raise AssertionError('require_llm=True accepted missing keys')
    finally:
        config.read_env_file = old
    print('ok   test_config_without_credentials_for_non_llm_modes')


def test_reset_refuses_output_containing_source(tmp):
    # output_dir == tmp, and the source lives at tmp/src: deleting the
    # output would delete the source tree.
    cfg = {
        'output_dir': tmp,
        'source_dir': os.path.join(tmp, 'src'),
    }
    os.makedirs(cfg['source_dir'], exist_ok=True)
    try:
        outputs.reset_output(cfg)
    except SystemExit:
        print('ok   test_reset_refuses_output_containing_source')
        return
    raise AssertionError('reset_output deleted a directory containing source')


def main():
    tests = [
        test_no_llm_stub_never_overwrites_real_prose,
        test_render_filters_stale_and_disabled_records,
        test_config_without_credentials_for_non_llm_modes,
        test_reset_output_keeps_doc_cache_and_prunes,
        test_reset_refuses_output_containing_source,
    ]
    for fn in tests:
        with tempfile.TemporaryDirectory() as tmp:
            fn(tmp)
    print(f'\n{len(tests)} cache-safety tests passed')


if __name__ == '__main__':
    main()
