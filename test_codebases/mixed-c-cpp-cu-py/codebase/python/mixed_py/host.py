"""Entry point that wires Python, the C++ extension, the C core and CUDA."""
from .bridge import CNative, Engine


def run_demo(size: int = 1024, steps: int = 8) -> int:
    """Create an engine, run a few steps, and mix in a direct C call."""
    engine = Engine(size)
    total = 0
    for value in range(steps):
        total += engine.step(value)
    core = CNative("build/libmixed_core.so")
    return total + core.add(1, 2)


def describe_demo(size: int = 16) -> str:
    """Exercise the C++ describe() path from Python."""
    engine = Engine(size)
    return engine.describe(size)


if __name__ == "__main__":
    print(run_demo())
    print(describe_demo())
