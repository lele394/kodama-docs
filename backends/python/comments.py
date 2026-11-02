"""Comment cleaning for Python developer comments."""
import re

from .nodes import node_text


def comment_text(node):
    """Cleaned comment text: leading '#' marker(s) and one space removed."""
    return re.sub(r'^\s*#+\s?', '', node_text(node)).strip()
