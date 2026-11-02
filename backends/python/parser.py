"""tree-sitter-python parser instance."""

import tree_sitter_python as tspy
from tree_sitter import Language, Parser

parser = Parser(Language(tspy.language()))
