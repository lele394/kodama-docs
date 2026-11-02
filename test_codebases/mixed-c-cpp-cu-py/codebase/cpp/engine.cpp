#include "engine.hpp"
#include "../c/core.h"

#include <string>

namespace mixed {

/* Construct an engine with a fixed element count. */
Engine::Engine(int size) : size_(size), steps_(0) {}

Engine::~Engine() {}

/* Advance the engine: call C, then scale the result. */
int Engine::step(int value) {
    steps_++;
    return c_scale(c_add(value, size_), 2);
}

/* Hand the buffers to the CUDA launcher. */
void Engine::run_gpu(float a, float* x, float* y) {
    launch_saxpy(a, x, y, size_);
}

int Engine::size() const {
    return size_;
}

/* Build a one-line description, clamped to a sane step count. */
std::string Engine::describe(int value) const {
    int bounded = clamp_value(value, 0, steps_ + 1);
    return "engine(" + std::to_string(size_) + ") step " +
           std::to_string(bounded);
}

/*
kodama-docs-llm:skip
Legacy entry point kept for ABI compatibility; skip LLM generation.
*/
int Engine::legacy_entry(int value) {
    return value;
}

}  // namespace mixed
