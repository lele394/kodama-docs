"""A module and a function share the name `utils` in one file: the
`utils.run(...)` method call goes to the imported module, the bare
`utils()` call to the local function. (inert: runtime can't bind both.)"""
import utils


def utils():
    return 'local-utils'


def trap():
    a = utils.run(['x'])   # expect: resolved utils.py::run
    b = utils()            # expect: resolved inert/utilscol.py::utils
    return a, b
