#include "engine.hpp"
#include "../c/core.h"

#include <pybind11/pybind11.h>

namespace py = pybind11;

/* Python-facing add: forwards to the C core. */
static int py_add(int a, int b) {
    return c_add(a, b);
}

/* Python module initializer. The macro looks like a function to tree-sitter,
 * which is useful here: the binding block itself gets documented. */
PYBIND11_MODULE(mixed_native, m) {
    m.doc() = "Native bridge for the mixed C/C++/CUDA sample";
    m.def("add", &py_add, "Add two integers through the C core");
    py::class_<mixed::Engine>(m, "Engine")
        .def(py::init<int>())
        .def("step", &mixed::Engine::step)
        .def("run_gpu", &mixed::Engine::run_gpu)
        .def("size", &mixed::Engine::size)
        .def("describe", &mixed::Engine::describe);
}
