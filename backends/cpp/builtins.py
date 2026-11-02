"""Names the C-family resolver treats as builtins / standard library.

These are not project symbols: a call to one stays a ``builtin`` graph node
instead of becoming a dangling project reference. ``std`` covers every
``std::...`` call through the graph's namespace handling.
"""

BUILTIN_NAMES = {
    # C / C++ keywords that can appear in callee position
    'NULL', 'nullptr', 'true', 'false', 'this', 'void', 'sizeof',
    # common libc
    'printf', 'fprintf', 'sprintf', 'snprintf', 'vprintf', 'vfprintf',
    'scanf', 'sscanf', 'puts', 'putchar', 'getchar', 'perror',
    'malloc', 'calloc', 'realloc', 'free', 'memcpy', 'memmove', 'memset',
    'memcmp', 'strlen', 'strcmp', 'strncmp', 'strcpy', 'strncpy', 'strcat',
    'strncat', 'strchr', 'strrchr', 'strstr', 'strtok', 'strerror',
    'atoi', 'atol', 'atoll', 'atof', 'strtol', 'strtoul', 'strtod',
    'abs', 'labs', 'llabs', 'fabs', 'fabsf', 'sqrt', 'sqrtf', 'pow',
    'powf', 'sin', 'sinf', 'cos', 'cosf', 'tan', 'tanf', 'exp', 'expf',
    'log', 'logf', 'log2', 'log10', 'floor', 'floorf', 'ceil', 'ceilf',
    'round', 'roundf', 'trunc', 'fmod', 'fmodf', 'fma', 'fmaf',
    'rand', 'srand', 'time', 'clock', 'getenv', 'exit', 'abort', 'assert',
    'fopen', 'fclose', 'fread', 'fwrite', 'fflush', 'fseek', 'ftell',
    'fgets', 'fputs', 'open', 'close', 'read', 'write',
    # C++ std namespace (base name; std::foo is handled as a namespace)
    'std',
    # CUDA runtime / driver API
    'cudaMalloc', 'cudaMallocManaged', 'cudaMallocHost', 'cudaHostAlloc',
    'cudaFree', 'cudaFreeHost', 'cudaMemcpy', 'cudaMemcpyAsync',
    'cudaMemset', 'cudaMemsetAsync', 'cudaDeviceSynchronize',
    'cudaStreamSynchronize', 'cudaStreamCreate', 'cudaStreamDestroy',
    'cudaStreamWaitEvent', 'cudaEventCreate', 'cudaEventDestroy',
    'cudaEventRecord', 'cudaEventSynchronize', 'cudaEventElapsedTime',
    'cudaGetLastError', 'cudaPeekAtLastError', 'cudaGetDeviceCount',
    'cudaGetDeviceProperties', 'cudaSetDevice', 'cudaGetDevice',
    'cudaDeviceReset', 'cudaMemGetInfo', 'cudaHostGetDevicePointer',
    # CUDA device builtins
    '__syncthreads', '__syncwarp', '__threadfence', '__threadfence_block',
    '__shfl_down_sync', '__shfl_up_sync', '__shfl_xor_sync', '__shfl_sync',
    'atomicAdd', 'atomicSub', 'atomicExch', 'atomicMin', 'atomicMax',
    'atomicInc', 'atomicDec', 'atomicCAS', 'atomicAnd', 'atomicOr',
    'atomicXor',
    'threadIdx', 'blockIdx', 'blockDim', 'gridDim', 'warpSize',
    'rsqrtf', '__fdividef', '__expf', '__logf', '__log2f', '__sinf',
    '__cosf', '__tanf', '__powf', '__saturatef',
}
