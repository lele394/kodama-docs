#ifndef MIXED_KERNELS_CUH
#define MIXED_KERNELS_CUH

#ifdef __cplusplus
extern "C" {
#endif

/* Launch the SAXPY kernel on the default stream. */
void launch_saxpy(float a, const float* x, float* y, int n);

#ifdef __cplusplus
}
#endif

#endif /* MIXED_KERNELS_CUH */
