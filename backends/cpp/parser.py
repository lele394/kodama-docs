"""tree-sitter parser selection and C/C++/CUDA dialect detection."""
import os
import re

import tree_sitter_cpp as tscpp
import tree_sitter_cuda as tscuda
from tree_sitter import Language, Parser

from .constants import CUDA_EXTS

_CPP_PARSER = Parser(Language(tscpp.language()))
_CUDA_PARSER = Parser(Language(tscuda.language()))


def parser_for(relpath):
    """The parser that handles this path (.cu/.cuh use the CUDA grammar)."""
    return _CUDA_PARSER if \
        os.path.splitext(relpath)[1].lower() in CUDA_EXTS else _CPP_PARSER


def dialect(relpath, source=''):
    """``c``, ``cpp`` or ``cuda`` for display/diagnostics."""
    ext = os.path.splitext(relpath)[1].lower()
    if ext in CUDA_EXTS:
        return 'cuda'
    if ext == '.c':
        return 'c'
    if ext == '.h':
        # .h is ambiguous. C++-only constructs are a strong signal; plain
        # extern "C" headers stay C.
        if re.search(r'\b(class|namespace|template|public|private|'
                     r'protected)\b|::|\bstd\b', source):
            return 'cpp'
        return 'c'
    return 'cpp'
