#ifndef MIXED_ENGINE_HPP
#define MIXED_ENGINE_HPP

#include "../c/core.h"
#include "../cuda/kernels.cuh"
#include "math.hpp"

#include <string>
#include <vector>

namespace mixed {

/* Small stateful engine that ties the C core and the CUDA launcher together. */
class Engine {
public:
    explicit Engine(int size);
    ~Engine();

    /* Advance one step through the C core. */
    int step(int value);

    /* Run the GPU path through the CUDA launcher. */
    void run_gpu(float a, float* x, float* y);

    /* Number of elements this engine owns. */
    int size() const;

    /* Human-readable description; uses std::to_string and clamp_value. */
    std::string describe(int value) const;

private:
    int size_;
    int steps_;
};

}  // namespace mixed

#endif /* MIXED_ENGINE_HPP */
