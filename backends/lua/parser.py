"""tree-sitter-lua parser instance."""

import tree_sitter_lua as tslua
from tree_sitter import Language, Parser

parser = Parser(Language(tslua.language()))
