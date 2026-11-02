#include "kernels.cuh"
#include <cuda_runtime.h>

/* One SAXPY element per thread: y[i] = a * x[i] + y[i]. */
__global__ void saxpy_kernel(float a, const float* x, float* y, int n) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < n) {
        y[i] = a * x[i] + y[i];
    }
}

/* Warp-level reduction used by the (imaginary) fused kernel. */
__device__ float warp_sum(float value) {
    for (int offset = warpSize / 2; offset > 0; offset >>= 1) {
        value += __shfl_down_sync(0xffffffff, value, offset);
    }
    return value;
}

/* Launch the kernel and wait for it, so the C++ caller sees a simple API. */
void launch_saxpy(float a, const float* x, float* y, int n) {
    int blocks = (n + 255) / 256;
    saxpy_kernel<<<blocks, 256>>>(a, x, y, n);
    cudaDeviceSynchronize();
}
