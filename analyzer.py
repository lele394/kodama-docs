"""Deterministic Lua source analysis: tokenizer, parser, extractor.

Zero LLM involvement. Pure stdlib. Raises ParseError on bad syntax (caller
resyncs per line).
"""
import re


class ParseError(Exception):
    def __init__(self, msg, line=0):
        super().__init__(msg)
        self.line = line


# ---------------------------------------------------------------- tokenizer

class Token:
    __slots__ = ('kind', 'value', 'line')

    def __init__(self, kind, value, line):
        self.kind = kind      # 'name' | 'num' | 'str' | 'punct' | 'eof'
        self.value = value
        self.line = line

    def __repr__(self):
        return f'Tok({self.kind},{self.value!r},{self.line})'


_NUM = re.compile(r'0[xX][0-9a-fA-F]+(?:\.[0-9a-fA-F]+)?(?:[pP][+-]?\d+)?'
                  r'|(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?')
_ID = re.compile(r'[A-Za-z_]\w*')

_OPS2 = ('..', '...', '==', '~=', '<=', '>=', '::', '<<', '>>')
_OPS1 = set('(){}[]<>+-*/%^#;:=,.')


def tokenize(src: str):
    toks = []
    line = 1
    i, n = 0, len(src)

    def skip_newlines(s):
        nonlocal line
        line += s.count('\n')

    while i < n:
        c = src[i]
        # whitespace
        if c in ' \t\r\n':
            m = re.match(r'[ \t\r\n]+', src[i:])
            skip_newlines(m.group(0))
            i += len(m.group(0))
            continue
        # comments
        if src.startswith('--', i):
            if src.startswith('--[', i):
                m = re.match(r'--\[=*\[', src[i:])
                if m:
                    open_seq = m.group(0)
                    lvl = len(open_seq) - 4  # '=' count
                    close = ']' + '=' * lvl + ']'
                    end = src.find(close, i + len(open_seq))
                    if end == -1:
                        skip_newlines(src[i:])
                        break
                    skip_newlines(src[i:end])
                    i = end + len(close)
                    continue
            end = src.find('\n', i)
            end = n if end == -1 else end
            if end > i:
                skip_newlines(src[i:end])
            i = end
            continue
        # long strings  [[ ... ]]  [=[ ... ]=]  (a lone '[' is a table index)
        if src.startswith('[[', i) or src.startswith('[=', i):
            m = re.match(r'\[[=]*\[', src[i:])
            open_seq = m.group(0)
            lvl = len(open_seq) - 2
            close = ']' + '=' * lvl + ']'
            end = src.find(close, i + len(open_seq))
            if end == -1:
                skip_newlines(src[i:])
                raise ParseError('unterminated long string', line)
            skip_newlines(src[i:end + len(close)])
            toks.append(Token('str', src[i:end + len(close)], line))
            i = end + len(close)
            continue
        # short strings
        if c in '"\'':
            q = c
            j = i + 1
            while j < n:
                if src[j] == '\\':
                    j += 2
                    continue
                if src[j] == q:
                    break
                if src[j] == '\n':
                    raise ParseError('unterminated string', line)
                j += 1
            if j >= n:
                raise ParseError('unterminated string', line)
            toks.append(Token('str', src[i:j + 1], line))
            i = j + 1
            continue
        # numbers
        if c.isdigit() or (c == '.' and i + 1 < n and src[i + 1].isdigit()):
            m = _NUM.match(src, i)
            if not m:
                raise ParseError(f'bad number at {i}', line)
            toks.append(Token('num', m.group(0), line))
            i = m.end()
            continue
        # identifiers / keywords
        if c.isalpha() or c == '_':
            m = _ID.match(src, i)
            toks.append(Token('name', m.group(0), line))
            i = m.end()
            continue
        # operators / punctuation (check 3-char before 2-char)
        if src.startswith('...', i):
            toks.append(Token('punct', '...', line))
            i += 3
            continue
        two = src[i:i + 2]
        if two in _OPS2:
            toks.append(Token('punct', two, line))
            i += 2
            continue
        if c in _OPS1:
            toks.append(Token('punct', c, line))
            i += 1
            continue
        raise ParseError(f'bad char {c!r}', line)
    toks.append(Token('eof', None, line))
    return toks


# ---------------------------------------------------------------- parser
# Recursive descent over the token list. Produces a dict AST where every
# node carries 'line'. Only structure is modeled — enough for scoping and
# symbol extraction, not for code generation.

NAME_KEYS = {'function', 'if', 'while', 'do', 'for', 'repeat', 'local',
             'return', 'break', 'goto'}


class Parser:
    def __init__(self, toks):
        self.toks = toks
        self.pos = 0

    def peek(self, k=0):
        return self.toks[min(self.pos + k, len(self.toks) - 1)]

    def at(self, kind, value=None):
        t = self.peek()
        if t.kind != kind:
            return False
        return value is None or t.value == value

    def eat(self, kind, value=None):
        t = self.peek()
        if t.kind != kind or (value is not None and t.value != value):
            raise ParseError(f'expected {value or kind}, got {t.value!r}', t.line)
        self.pos += 1
        return t

    def skip(self, kind, value=None):
        t = self.peek()
        if t.kind == kind and (value is None or t.value == value):
            self.pos += 1
            return True
        return False

    # --- statements ---
    def parse_block(self):
        stmts = []
        while True:
            t = self.peek()
            if t.kind == 'eof' or (t.kind == 'name' and t.value in
                                  ('end', 'until', 'else', 'elseif')):
                break
            if t.kind == 'punct' and t.value == ';':
                self.pos += 1
            elif t.kind == 'name' and t.value == 'break':
                self.pos += 1
                stmts.append({'type': 'break', 'line': t.line})
            elif t.kind == 'name' and t.value == 'return':
                self.pos += 1
                values = []
                if not self.at('name', 'end') and not self.at('eof') and \
                   not self._at_block_end():
                    values.append(self.parse_expr())
                    while self.skip('punct', ','):
                        values.append(self.parse_expr())
                stmts.append({'type': 'return', 'values': values,
                              'line': t.line})
            elif t.kind == 'name' and t.value == 'goto':
                self.pos += 1
                stmts.append({'type': 'goto', 'label': self.eat('name').value,
                              'line': t.line})
            elif t.kind == 'punct' and t.value == '::':
                self.pos += 1
                lbl = self.eat('name').value
                self.eat('punct', '::')
                stmts.append({'type': 'label', 'name': lbl, 'line': t.line})
            elif t.kind == 'name' and t.value in NAME_KEYS:
                stmts.append(self.parse_kw(t.value))
            else:
                stmts.append(self.parse_simple())
        return {'type': 'block', 'stmts': stmts}

    def _at_block_end(self):
        t = self.peek()
        return t.kind == 'eof' or (t.kind == 'name' and t.value in
                                   ('end', 'until', 'else', 'elseif',
                                    'break', 'return')) or \
            (t.kind == 'punct' and t.value == ';')

    def parse_kw(self, kw):
        if kw == 'function':
            return self.parse_function()
        if kw == 'if':
            return self.parse_if()
        if kw in ('while', 'do'):
            return self.parse_loop(kw)
        if kw == 'for':
            return self.parse_for()
        if kw == 'repeat':
            return self.parse_repeat()
        if kw == 'local':
            return self.parse_local()
        return self.parse_simple()

    def parse_simple(self):
        line = self.peek().line
        # function call statement or assignment: expr-list (= value-list)?
        targets = [self.parse_expr()]
        while self.at('punct', ','):
            self.pos += 1
            targets.append(self.parse_expr())
        if self.skip('punct', '='):
            values = [self.parse_expr()]
            while self.skip('punct', ','):
                values.append(self.parse_expr())
            return {'type': 'assign', 'targets': targets, 'values': values,
                    'line': line}
        # must be a call for this to be a statement
        for t in targets:
            if t.get('type') != 'call':
                raise ParseError('expected call or assignment', line)
        c = targets[0]
        if 'fn' not in c:
            c = dict(c)
            c['fn'] = None
        return c

    def parse_function(self):
        self.eat('name', 'function')
        line = self.peek().line
        name = self.parse_dotted_name()
        method = None
        if self.skip('punct', ':'):
            method = self.eat('name').value
            name = name + [method]
        node = {'type': 'funcdef', 'name': name, 'method': method, 'line': line,
                **self.parse_body()}
        return node

    def parse_local(self):
        self.eat('name', 'local')
        line = self.peek().line
        if self.skip('name', 'function'):
            name = self.parse_dotted_name()
            return {'type': 'localfunc', 'name': name, 'line': line,
                    **self.parse_body()}
        names = [self.peek().value]
        self.eat('name')
        while self.skip('punct', ','):
            names.append(self.eat('name').value)
        if self.skip('punct', '='):
            values = [self.parse_expr()]
            while self.skip('punct', ','):
                values.append(self.parse_expr())
            return {'type': 'local', 'names': names, 'values': values,
                    'line': line}
        return {'type': 'local', 'names': names, 'values': [], 'line': line}

    def parse_if(self):
        self.eat('name', 'if')
        line = self.peek().line
        cond = self.parse_expr()
        self.eat('name', 'then')
        body = self.parse_block()
        els = []
        while self.skip('name', 'elseif'):
            c = self.parse_expr()
            self.eat('name', 'then')
            els.append({'cond': c, 'body': self.parse_block()})
        if self.skip('name', 'else'):
            els.append({'cond': None, 'body': self.parse_block()})
        self.eat('name', 'end')
        return {'type': 'if', 'cond': cond, 'body': body, 'els': els,
                'line': line}

    def parse_loop(self, kw):
        self.eat('name', kw)
        line = self.peek().line
        if kw == 'while':
            cond = self.parse_expr()
            self.eat('name', 'do')
        else:
            cond = None
        body = self.parse_block()
        self.eat('name', 'end')
        return {'type': kw, 'cond': cond, 'body': body, 'line': line}

    def parse_for(self):
        self.eat('name', 'for')
        line = self.peek().line
        var = self.eat('name').value
        if self.skip('punct', '='):
            init = self.parse_expr()
            self.eat('punct', ',')
            limit = self.parse_expr()
            step = None
            if self.skip('punct', ','):
                step = self.parse_expr()
        else:
            names = [var]
            while self.skip('punct', ','):
                names.append(self.eat('name').value)
            self.eat('name', 'in')
            iters = [self.parse_expr()]
            while self.skip('punct', ','):
                iters.append(self.parse_expr())
            init = limit = step = None
        self.eat('name', 'do')
        body = self.parse_block()
        self.eat('name', 'end')
        node = {'type': 'for', 'line': line, 'body': body}
        if init is not None and limit is not None:
            node.update(var=var, init=init, limit=limit, step=step)
        else:
            node.update(names=names, iters=iters)
        return node

    def parse_repeat(self):
        self.eat('name', 'repeat')
        line = self.peek().line
        body = self.parse_block()
        self.eat('name', 'until')
        cond = self.parse_expr()
        return {'type': 'repeat', 'body': body, 'cond': cond, 'line': line}

    # --- expressions (precedence climbing) ---
    def parse_expr(self):
        return self.parse_or()

    def parse_or(self):
        left = self.parse_and()
        while self.skip('name', 'or'):
            left = {'type': 'binop', 'op': 'or', 'a': left,
                    'b': self.parse_and(), 'line': left['line']}
        return left

    def parse_and(self):
        left = self.parse_cmp()
        while self.skip('name', 'and'):
            left = {'type': 'binop', 'op': 'and', 'a': left,
                    'b': self.parse_cmp(), 'line': left['line']}
        return left

    def parse_cmp(self):
        left = self.parse_concat()
        while True:
            t = self.peek()
            if t.kind == 'punct' and t.value in ('==', '~=', '<', '>', '<=', '>='):
                self.pos += 1
                left = {'type': 'binop', 'op': t.value, 'a': left,
                        'b': self.parse_concat(), 'line': left['line']}
            else:
                break
        return left

    def parse_concat(self):
        left = self.parse_add()
        while self.skip('punct', '..'):
            left = {'type': 'binop', 'op': '..', 'a': left,
                    'b': self.parse_add(), 'line': left['line']}
        return left

    def parse_add(self):
        left = self.parse_mul()
        while True:
            t = self.peek()
            if t.kind == 'punct' and t.value in ('+', '-'):
                self.pos += 1
                left = {'type': 'binop', 'op': t.value, 'a': left,
                        'b': self.parse_mul(), 'line': left['line']}
            else:
                break
        return left

    def parse_mul(self):
        left = self.parse_unary()
        while True:
            t = self.peek()
            if t.kind == 'punct' and t.value in ('*', '/', '%'):
                self.pos += 1
                left = {'type': 'binop', 'op': t.value, 'a': left,
                        'b': self.parse_unary(), 'line': left['line']}
            else:
                break
        return left

    def parse_unary(self):
        t = self.peek()
        if t.kind == 'punct' and t.value in ('-', '#'):
            self.pos += 1
            return {'type': 'unary', 'op': t.value, 'a': self.parse_unary(),
                    'line': t.line}
        if t.kind == 'name' and t.value == 'not':
            self.pos += 1
            return {'type': 'unary', 'op': 'not', 'a': self.parse_unary(),
                    'line': t.line}
        return self.parse_pow()

    def parse_pow(self):
        left = self.parse_postfix()
        if self.at('punct', '^'):
            self.pos += 1
            left = {'type': 'binop', 'op': '^', 'a': left,
                    'b': self.parse_pow(), 'line': left['line']}
        return left

    def parse_postfix(self):
        node = self.parse_primary()
        while True:
            t = self.peek()
            if t.kind == 'punct' and t.value == '.':
                self.pos += 1
                name = self.eat('name').value
                if node.get('type') == 'dotted':
                    node['parts'].append(name)
                else:
                    node = {'type': 'dotted', 'parts': [node, name],
                            'line': node['line']}
            elif t.kind == 'punct' and t.value == '[':
                self.pos += 1
                idx = self.parse_expr()
                self.eat('punct', ']')
                node = {'type': 'index', 'obj': node, 'idx': idx,
                        'line': node['line']}
            elif t.kind == 'punct' and t.value == ':':
                self.pos += 1
                method = self.eat('name').value
                args = self.parse_args()
                node = {'type': 'call', 'fn': node, 'args': args,
                        'method': method, 'line': node['line']}
            elif t.kind == 'punct' and t.value in ('(', '{'):
                args = self.parse_args()
                node = {'type': 'call', 'fn': node, 'args': args,
                        'line': node['line']}
            else:
                break
        return node

    def parse_args(self):
        t = self.peek()
        if t.value == '(':
            self.eat('punct', '(')
            if self.skip('punct', ')'):
                return []
            args = [self.parse_expr()]
            while self.skip('punct', ','):
                args.append(self.parse_expr())
            self.eat('punct', ')')
            return args
        if t.value == '{':
            return [self.parse_table()]
        raise ParseError(f'expected argument list, got {t.value!r}', t.line)

    def parse_primary(self):
        t = self.peek()
        if t.kind == 'name':
            if t.value == 'function':
                self.pos += 1
                body = self.parse_body()
                return {'type': 'closure', 'line': t.line, **body}
            self.pos += 1
            return {'type': 'name', 'name': t.value, 'line': t.line}
        if t.kind in ('num', 'str'):
            self.pos += 1
            return {'type': t.kind, 'value': t.value, 'line': t.line}
        if t.kind == 'punct' and t.value == '...':
            self.pos += 1
            return {'type': 'vararg', 'line': t.line}
        if t.kind == 'punct':
            if t.value == '(':
                self.pos += 1
                e = self.parse_expr()
                self.eat('punct', ')')
                return e
            if t.value == '{':
                return self.parse_table()
        raise ParseError(f'expected expression, got {t.value!r}', t.line)

    def parse_table(self):
        self.eat('punct', '{')
        line = self.peek().line
        fields = []
        while not self.at('punct', '}'):
            t = self.peek()
            if t.kind == 'name' and t.value not in NAME_KEYS and \
                    self.peek(1).value == '=':
                key = self.eat('name').value
                while self.skip('punct', '.'):
                    key += '.' + self.eat('name').value
                self.eat('punct', '=')
                fields.append({'key': key, 'val': self.parse_expr()})
            elif t.kind == 'punct' and t.value == '[':
                self.pos += 1
                idx = self.parse_expr()
                self.eat('punct', ']')
                self.eat('punct', '=')
                fields.append({'key': None, 'val': self.parse_expr(),
                               'idx': idx})
            else:
                fields.append({'key': None, 'val': self.parse_expr()})
            if not self.skip('punct', ',') and not self.skip('punct', ';'):
                break
        self.eat('punct', '}')
        return {'type': 'table', 'fields': fields, 'line': line}

    def parse_dotted_name(self):
        parts = [self.eat('name').value]
        while self.skip('punct', '.'):
            parts.append(self.eat('name').value)
        return parts

    def parse_body(self):
        self.eat('punct', '(')
        params = []
        vararg = False
        if not self.at('punct', ')'):
            while True:
                t = self.peek()
                if t.kind == 'punct' and t.value == '...':
                    vararg = True
                    self.pos += 1
                    break
                params.append(self.eat('name').value)
                if not self.skip('punct', ','):
                    break
        self.eat('punct', ')')
        body = self.parse_block()
        end_tok = self.peek()
        self.eat('name', 'end')
        return {'params': params, 'vararg': vararg, 'body': body,
                'end_line': end_tok.line}

    def parse(self):
        block = self.parse_block()
        if self.peek().kind != 'eof':
            raise ParseError(f'trailing tokens at {self.peek().value!r}',
                             self.peek().line)
        return block


def parse_lua(source: str) -> dict:
    if source.startswith('\ufeff'):
        source = source[1:]
    return Parser(tokenize(source)).parse()


# --------------------------------------------------------------- extractor

BUILTIN_NAMES = {
    'print', 'pairs', 'ipairs', 'next', 'type', 'tonumber', 'tostring',
    'pcall', 'xpcall', 'error', 'assert', 'select', 'unpack', 'rawget',
    'rawset', 'rawequal', 'setmetatable', 'getmetatable', 'require',
    'dofile', 'collectgarbage', 'self', '_G', '_VERSION', 'math', 'string',
    'table', 'os', 'io', 'coroutine', 'bit32', 'utf8', 'module',
}


def _target_name(target: dict):
    t = target.get('type')
    if t == 'name':
        return target['name']
    if t == 'dotted':
        parts = [p for p in target['parts'] if isinstance(p, str)]
        return parts[-1] if parts else None
    if t == 'index':
        return _target_name(target['obj'])
    return None


def _classify(values) -> str:
    if not values:
        return 'empty'
    v = values[0]
    t = v.get('type')
    if t == 'table':
        return 'table'
    if t == 'str':
        return 'string'
    if t == 'num':
        return 'number'
    if t == 'closure' or t == 'funcdef':
        return 'function'
    if t == 'call':
        return 'call'
    return 'expr'


def extract(source: str, relpath: str) -> dict:
    """Deterministic symbol extraction from a parsed source."""
    ast = parse_lua(source)
    fns, file_vars, calls, imports = [], [], [], []
    seen_fn, seen_call = set(), set()

    def add_fn(name, qual, line, end_line, params, vararg):
        fname = name or 'anon'
        fid = f'fn:{relpath}::{fname}@{line}'
        if fid in seen_fn:
            return
        seen_fn.add(fid)
        fns.append({
            'id': fid,
            'name': fname,
            'qualified': qual or fname,
            'line': line,
            'end_line': end_line or line,
            'params': list(params or []),
            'vararg': bool(vararg),
        })

    def note_call(node):
        fn = node.get('fn')
        if not fn or not isinstance(fn, dict):
            return
        name = None
        if fn.get('type') == 'name':
            name = fn['name']
        elif fn.get('type') == 'dotted':
            name = '.'.join(p for p in fn['parts'] if isinstance(p, str))
        if not name:
            return
        key = (name, node['line'])
        if key in seen_call:
            return
        seen_call.add(key)
        calls.append({'callee': name, 'line': node['line'],
                      'method': node.get('method')})
        if fn.get('type') == 'name' and fn['name'] not in BUILTIN_NAMES:
            pass  # tracked via callee list

    def walk(node, depth):
        if not isinstance(node, dict):
            return
        t = node.get('type')
        if t in ('funcdef', 'localfunc'):
            qual = '.'.join(node['name'])
            add_fn(node['name'][-1], qual, node['line'], node.get('end_line'),
                   node['params'], node['vararg'])
            walk(node['body'], depth + 1)
            return
        if t == 'closure':
            walk(node['body'], depth + 1)
            return
        if t == 'local':
            names = node.get('names') or []
            values = node.get('values') or []
            for v in values:
                if v.get('type') == 'closure':
                    add_fn(names[0] if names else None,
                           names[0] if names else None, v['line'],
                           v.get('end_line'), v['params'], v['vararg'])
                    walk(v, depth + 1)
                else:
                    walk(v, depth)
            if depth == 0:
                for nm in names:
                    file_vars.append({'name': nm, 'line': node['line'],
                                      'init': _classify(values)})
            return
        if t == 'assign':
            targets = node.get('targets') or []
            tname = _target_name(targets[0]) if targets else None
            for v in node.get('values') or []:
                if v.get('type') == 'closure':
                    add_fn(tname, tname, v['line'], v.get('end_line'),
                           v['params'], v['vararg'])
                    walk(v, depth + 1)
                else:
                    walk(v, depth)
            return
        if t == 'call':
            note_call(node)
            first_str = next((a for a in node.get('args') or []
                              if isinstance(a, dict) and a.get('type') == 'str'),
                             None)
            if first_str is not None and depth <= 1:
                fn = node.get('fn')
                base = None
                if isinstance(fn, dict):
                    if fn.get('type') == 'name':
                        base = fn['name']
                    elif fn.get('type') == 'dotted':
                        parts = fn.get('parts') or []
                        base = parts[-1] if isinstance(parts[-1], str) \
                            else None
                if base in ('require', 'dofile'):
                    val = first_str['value'].strip().strip('"')
                    if val and val not in [x['module'] for x in imports]:
                        imports.append({'module': val,
                                        'line': first_str.get('line',
                                                              node['line'])})
            fn = node.get('fn')
            callee_base = None
            if isinstance(fn, dict):
                if fn.get('type') == 'dotted':
                    last = fn['parts'][-1] if fn['parts'] else None
                    callee_base = last if isinstance(last, str) else None
                elif fn.get('type') == 'name':
                    callee_base = fn['name']
            for a in node.get('args') or []:
                if isinstance(a, dict) and a.get('type') == 'closure':
                    add_fn(callee_base, callee_base, a['line'],
                           a.get('end_line'), a['params'], a['vararg'])
                    walk(a, depth + 1)
                else:
                    walk(a, depth)
            return
        if t == 'table':
            for f in node.get('fields') or []:
                val = f.get('val')
                if isinstance(val, dict) and val.get('type') == 'closure':
                    add_fn(f.get('key'), f.get('key'), val['line'],
                           val.get('end_line'), val['params'], val['vararg'])
                    walk(val, depth + 1)
                else:
                    walk(val, depth)
                    if isinstance(f.get('idx'), dict):
                        walk(f['idx'], depth)
            return
        if t == 'block':
            for s in node.get('stmts') or []:
                walk(s, depth)
            return
        if t == 'if':
            walk(node.get('cond'), depth)
            walk(node.get('body'), depth)
            for e in node.get('els') or []:
                if isinstance(e.get('cond'), dict):
                    walk(e['cond'], depth)
                walk(e.get('body'), depth)
            return
        if t in ('while', 'do', 'for', 'repeat'):
            for k in ('cond', 'init', 'limit', 'step'):
                if isinstance(node.get(k), dict):
                    walk(node[k], depth)
            if t == 'for':
                for k in ('iters',):
                    for it in node.get(k) or []:
                        walk(it, depth)
            walk(node.get('body'), depth)
            return
        if t == 'return':
            for v in node.get('values') or []:
                walk(v, depth)
            return
        # generic: binop, unary, dotted, index, name, num, str, vararg
        for k, v in node.items():
            if isinstance(v, dict):
                walk(v, depth)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        walk(item, depth)

    walk(ast, 0)
    lines = source.splitlines()

    def body_of(rec):
        a, b = rec['line'] - 1, min(rec['end_line'], len(lines))
        return '\n'.join(lines[a:b])

    for rec in fns:
        rec['body'] = body_of(rec)
    return {'functions': fns, 'file_vars': file_vars, 'calls': calls,
            'imports': imports}
