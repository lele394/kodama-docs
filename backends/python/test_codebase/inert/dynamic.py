"""Dynamic receivers: the receiver is computed at runtime, so no static
target exists — but each call must stay VISIBLE as external (orange),
never silently dropped. (inert: `open`/`getattr` are never executed.)"""
cfg = {'k': {}}
obj = object()


def run():
    a = open('data.txt').read().strip()    # expect: external ?.read ?.strip
    cfg['k'].update({'a': 1})              # expect: external ?.update
    b = getattr(obj, 'wake')()             # expect: external ?
    g = lambda x: x(1)                     # expect: external x
    c = g(2)                               # expect: external g
    return a, b, c
