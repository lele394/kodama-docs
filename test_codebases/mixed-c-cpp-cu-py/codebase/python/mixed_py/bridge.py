"""Python side of the mixed sample: ctypes / pybind11 boundaries.

The native extension is built from ``cpp/bindings.cpp`` and the CUDA
launcher; the C core is loaded directly with ctypes. Nothing here needs to
run for the documentation checks — the module is parsed, not imported.
"""
import ctypes
from pathlib import Path

try:
    import mixed_native
except ImportError:  # the fixture is parsed, not built
    mixed_native = None


# Multiline developer comment on a Python class:
# loads the C core and exposes the ctypes wrappers.
class CNative:
    """Load the C core with ctypes and expose ``c_add``."""

    def __init__(self, library_path: str):
        self._path = Path(library_path)
        self._lib = ctypes.CDLL(str(self._path))
        self._lib.c_add.argtypes = [ctypes.c_int, ctypes.c_int]
        self._lib.c_add.restype = ctypes.c_int
        self._lib.c_scale.argtypes = [ctypes.c_int, ctypes.c_int]
        self._lib.c_scale.restype = ctypes.c_int

    def add(self, a: int, b: int) -> int:
        """Call the C ``c_add`` through ctypes."""
        return self._lib.c_add(a, b)

    def scale(self, value: int, factor: int) -> int:
        """Call the C ``c_scale`` through ctypes."""
        return self._lib.c_scale(value, factor)


class Engine:
    """Python facade over the C++ ``mixed::Engine`` extension."""

    def __init__(self, size: int, library_path: str = "build/libmixed_core.so"):
        self.size = size
        self._c = CNative(library_path)
        self._native = mixed_native.Engine(size) if mixed_native else None

    def step(self, value: int) -> int:
        """Prefer the C++ path, fall back to the C core."""
        if self._native is not None:
            return self._native.step(value)
        return self._c.scale(self._c.add(value, self.size), 2)

    def run_gpu(self, a: float, x, y) -> None:
        """Run the CUDA path through the C++ binding."""
        if self._native is not None:
            self._native.run_gpu(a, x, y)

    def describe(self, value: int) -> str:
        """Describe the engine, or synthesize a fallback string."""
        if self._native is not None:
            return self._native.describe(value)
        return f"engine({self.size}) step {value}"
