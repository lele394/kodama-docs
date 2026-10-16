"""Bundler tests (kodama_docs/js_bundle.py).

Run:  .venv/bin/python tests/test_js_bundle.py

Guards the ESM-to-classic bundler that makes the static site work over
file://: the supported import/export subset parses (aliases, multi-line
braces, inline comments), anything outside it is rejected loudly, import
cycles and missing modules are caught, and the two real bundles
(sidebar.js, graph.js) are syntactically valid node scripts (node
--check) and actually run with inline data and NO fetch — a DOM-stub
node harness, which is exactly the file:// situation the bundles exist
for.
"""
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from kodama_docs.js_bundle import bundle, parse_module  # noqa: E402

WEB = os.path.join(REPO, 'web')
FAILS = []
SKIPS = []


def check(cond, msg):
    if cond:
        print(f'ok   {msg}')
    else:
        print(f'FAIL {msg}')
        FAILS.append(msg)


def expect_raises(fn, msg):
    try:
        fn()
    except ValueError as e:
        check(True, f'{msg} -> {e}')
    except Exception as e:  # noqa: BLE001 - any error is acceptable here
        check(True, f'{msg} -> {type(e).__name__}: {e}')
    else:
        check(False, msg + '  (no error raised)')


def _node():
    return shutil.which('node')


# ------------------------------------------------------------------ subset
def test_parse_module_subset():
    p = parse_module(
        "import { a, b as c } from './x.js';\n"
        "import { d }\n"
        "  from './y.js';\n"
        'export function f() { return a; }\n'
        'export const G = 1;\n'
        'export { f as g, h };\n'
        "import { i, // trailing comment\n j } from './z.js';\n")
    check(p['imports'] == [('./x.js', [('a', 'a'), ('b', 'c')]),
                           ('./y.js', [('d', 'd')]),
                           ('./z.js', [('i', 'i'), ('j', 'j')])],
          'imports: alias, multi-line braces, inline comment')
    check(p['exports'] == [('f', 'f'), ('G', 'G'), ('g', 'f'), ('h', 'h')],
          'exports: declaration, list, list rename')

    expect_raises(lambda: parse_module("import x from './y.js';\n"),
                  'default import rejected')
    expect_raises(lambda: parse_module("export { a } from './x.js';\n"),
                  're-export rejected')
    expect_raises(lambda: parse_module('import("./x.js");\n'),
                  'dynamic import() rejected')
    expect_raises(lambda: parse_module('import.meta.url;\n'),
                  'import.meta rejected')
    expect_raises(lambda: parse_module('export default 1;\n'),
                  'export default rejected')


def test_bundle_errors(tmp):
    webdir = os.path.join(tmp, 'web_errors')
    os.makedirs(webdir)
    # import cycle
    with open(os.path.join(webdir, 'a.js'), 'w') as fh:
        fh.write("import { b } from './b.js';\nexport const a = 1;\n")
    with open(os.path.join(webdir, 'b.js'), 'w') as fh:
        fh.write("import { a } from './a.js';\nexport const b = 2;\n")
    expect_raises(lambda: bundle(webdir, 'a.js'), 'import cycle rejected')
    # missing module
    with open(os.path.join(webdir, 'a.js'), 'w') as fh:
        fh.write("import { x } from './nope.js';\nexport const a = 1;\n")
    expect_raises(lambda: bundle(webdir, 'a.js'), 'missing module rejected')
    # non-relative import
    with open(os.path.join(webdir, 'a.js'), 'w') as fh:
        fh.write("import { a } from 'lodash';\nexport const a = 1;\n")
    expect_raises(lambda: bundle(webdir, 'a.js'), 'bare specifier rejected')


def test_bundle_shape(tmp):
    webdir = os.path.join(tmp, 'web_shape')
    os.makedirs(webdir)
    with open(os.path.join(webdir, 'dep.js'), 'w') as fh:
        fh.write('export const x = 1;\nexport function f() { return x; }\n'
                 'export { x as alias };\n')
    with open(os.path.join(webdir, 'entry.js'), 'w') as fh:
        fh.write("import { x, f as ff } from './dep.js';\n"
                 'console.log(x + ff());\n')
    code = bundle(webdir, 'entry.js')
    check('__kodama_define' in code, 'shape: define registry present')
    check("'dep.js'" in code and "'entry.js'" in code,
          'shape: module ids as web/-relative posix paths')
    check('var { x, f: ff } = __kodama_require(\'dep.js\');' in code,
          'shape: import -> destructuring require (alias kept)')
    check('__kodama_exports.x = x;' in code, 'shape: exports registered')
    check('__kodama_exports.alias = x;' in code, 'shape: list rename kept')
    node = _node()
    if not node:
        SKIPS.append('node not on PATH')
        return None
    out = os.path.join(tmp, 'out')
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, 'entry.js'), 'w') as fh:
        fh.write(code)
    r = subprocess.run([node, os.path.join(out, 'entry.js')],
                       capture_output=True, text=True)
    check(r.returncode == 0 and '2' in r.stdout,
          f'tiny bundle executes (node says: {r.stdout.strip() or r.stderr.strip()})')
    return node


# ------------------------------------------------- real web/ bundles + node
HARNESS_SIDEBAR = r"""
'use strict';
const fs = require('fs');
class SNode {
  constructor(tag) { this.tagName=String(tag).toUpperCase(); this.className=''; this.children=[];
    this.parentNode=null; this.attrs={}; this.listeners={}; this.hidden=false; this.style={};
    this.href=''; this._text=''; this.value=''; }
  appendChild(c){ if(c.tagName==='#FRAGMENT'){for(const x of c.children.slice())this.appendChild(x);return this;}
    if(c.parentNode)c.parentNode.children.splice(c.parentNode.children.indexOf(c),1);
    c.parentNode=this; this.children.push(c); return c; }
  setAttribute(k,v){this.attrs[k]=String(v);}
  getAttribute(k){return k in this.attrs?this.attrs[k]:null;}
  addEventListener(t,fn){(this.listeners[t]=this.listeners[t]||[]).push(fn);}
  get nextElementSibling(){ if(!this.parentNode)return null;
    const i=this.parentNode.children.indexOf(this); return this.parentNode.children[i+1]||null; }
  querySelector(sel){ const cls=sel.replace(/^\./,'');
    const walk=n=>{ for(const c of n.children){ if(String(c.className).split(/\s+/).includes(cls))return c;
      const r=walk(c); if(r)return r; } return null; }; return walk(this); }
  get classList(){ const s=this; return { contains:c=>String(s.className).split(/\s+/).includes(c) }; }
  get textContent(){ return this._text; }
  set textContent(v){ this._text=v==null?'':String(v); this.children=[]; }
  focus(){} blur(){}
}
const byId={};
globalThis.document={
  createElement:t=>new SNode(t), createDocumentFragment:()=>new SNode('#fragment'),
  getElementById:id=>byId[id]||null, addEventListener:()=>{}, activeElement:null, body:new SNode('body'),
};
byId['sidebar']=new SNode('aside'); byId['sb-search']=new SNode('input'); byId['sb-tree']=new SNode('div');
globalThis.location={pathname:'/site/files/a.html',search:''};
const store=new Map();
globalThis.localStorage={getItem:k=>store.has(k)?store.get(k):null,setItem:(k,v)=>store.set(k,String(v)),removeItem:k=>store.delete(k)};
let fetchCalled=false;
globalThis.fetch=()=>{fetchCalled=true;throw new Error('file:// harness: fetch must not be called');};
globalThis.window={__KODAMA_BASE__:'../',
  __KODAMA_SYMBOLS__:{file_count:1,files:[{relpath:'a',lines:10,
    functions:[{name:'go',qualified:'go',line:4}],vars:[{name:'X',line:1}]}],manual:[]}};
const code=fs.readFileSync(process.argv[2],'utf8');
(0,eval)(code);
setTimeout(()=>{
  const tree=byId['sb-tree'];
  const fileRow=tree.children.find(n=>String(n.className).includes('sb-file'));
  if(!fileRow){console.error('FAIL: tree not rendered from inline data');process.exit(1);}
  if(fetchCalled){console.error('FAIL: fetch was called (inline data ignored)');process.exit(1);}
  const link=fileRow.children.find(n=>n.tagName==='A');
  if(!link||link.href!=='../files/a.html'){console.error('FAIL: wrong href',link&&link.href);process.exit(1);}
  console.log('BUNDLE-EXEC OK: tree rendered from inline symbols, no fetch, href',link.href);
  process.exit(0);
},50);
"""

HARNESS_GRAPH = r"""
'use strict';
const fs=require('fs');
class SNode{constructor(t){this.tagName=String(t).toUpperCase();this.className='';this.children=[];
 this.parentNode=null;this.attrs={};this.listeners={};this.style={};this.hidden=false;this._text='';}
 appendChild(c){c.parentNode=this;this.children.push(c);return c;}
 setAttribute(k,v){this.attrs[k]=String(v);} getAttribute(k){return k in this.attrs?this.attrs[k]:null;}
 addEventListener(){} get textContent(){return this._text;} set textContent(v){this._text=String(v);}
 set innerHTML(v){} get classList(){return {contains:()=>false};}}
globalThis.document={createElement:t=>new SNode(t),getElementById:()=>null,
  addEventListener:()=>{},body:new SNode('body'),activeElement:null};
globalThis.location={pathname:'/site/graph.html',search:''};
globalThis.window={__KODAMA_BASE__:'',__KODAMA_GRAPH__:{file_count:1,nodes:[],edges:[]}};
let fetchCalled=false;
globalThis.fetch=()=>{fetchCalled=true;throw new Error('no fetch under file://');};
(0,eval)(fs.readFileSync(process.argv[2],'utf8'));
setTimeout(()=>{ if(fetchCalled){console.error('FAIL: fetch called');process.exit(1);}
  console.log('GRAPH BUNDLE OK: evaluated cleanly, canvas absent -> safe no-op, no fetch');process.exit(0);},50);
"""


def test_real_bundles(tmp):
    node = _node()
    if not node:
        SKIPS.append('node not on PATH')
        return
    cases = (
        ('sidebar.js', ('sidebar.js', 'fuzzy.js', 'graph/util.js'),
         HARNESS_SIDEBAR, 'BUNDLE-EXEC OK'),
        ('graph.js', ('graph.js', 'graph/state.js', 'graph/draw.js'),
         HARNESS_GRAPH, 'GRAPH BUNDLE OK'),
    )
    for entry, must_contain, harness, marker in cases:
        code = bundle(WEB, entry)
        for mod in must_contain:
            check(f"'{mod}'" in code, f'{entry}: bundles module {mod}')
        check('__kodama_require(\'' + entry + '\')' in code,
              f'{entry}: entry module required last')
        bfile = os.path.join(tmp, entry)
        with open(bfile, 'w', encoding='utf-8') as fh:
            fh.write(code)
        r = subprocess.run([node, '--check', bfile],
                           capture_output=True, text=True)
        check(r.returncode == 0,
              f'{entry}: node --check passes'
              + ('' if r.returncode == 0 else f' ({r.stderr.strip()[:200]})'))
        hfile = os.path.join(tmp, 'harness_' + entry.replace('/', '_'))
        with open(hfile, 'w', encoding='utf-8') as fh:
            fh.write(harness)
        r = subprocess.run([node, hfile, bfile],
                           capture_output=True, text=True, timeout=60)
        check(r.returncode == 0 and marker in r.stdout,
              f'{entry}: executes in the file:// harness'
              + (f' ({r.stderr.strip()[:200]})' if r.returncode != 0 else ''))


def main():
    test_parse_module_subset()
    with tempfile.TemporaryDirectory() as tmp:
        test_bundle_errors(tmp)
        test_bundle_shape(tmp)
    with tempfile.TemporaryDirectory() as tmp:
        test_real_bundles(tmp)

    print()
    if SKIPS:
        for s in set(SKIPS):
            print(f'skip {s}')
    if FAILS:
        print(f'{len(FAILS)} assertion(s) FAILED')
        sys.exit(1)
    print('all js-bundle tests passed')


if __name__ == '__main__':
    main()
