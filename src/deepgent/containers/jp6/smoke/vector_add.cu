// Trivial CUDA kernel used two ways: compile-only in the container smoke
// check, and build-deploy-run-measure end to end by golden gt-0001 on the
// target board.
#include <cstdio>
#include <cstdlib>
#include <cuda_runtime.h>

#define CUDA_CHECK(call)                                                     \
    do {                                                                     \
        cudaError_t err_ = (call);                                           \
        if (err_ != cudaSuccess) {                                           \
            std::fprintf(stderr, "CUDA error %s at %s:%d: %s\n", #call,      \
                         __FILE__, __LINE__, cudaGetErrorString(err_));      \
            std::exit(1);                                                    \
        }                                                                    \
    } while (0)

__global__ void vector_add(const float* a, const float* b, float* c, int n) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < n) {
        c[i] = a[i] + b[i];
    }
}

int main() {
    const int n = 1 << 20;
    const size_t bytes = n * sizeof(float);

    float* host_a = static_cast<float*>(std::malloc(bytes));
    float* host_b = static_cast<float*>(std::malloc(bytes));
    float* host_c = static_cast<float*>(std::malloc(bytes));
    if (host_a == nullptr || host_b == nullptr || host_c == nullptr) {
        std::fprintf(stderr, "host allocation failed\n");
        return 1;
    }
    for (int i = 0; i < n; ++i) {
        host_a[i] = static_cast<float>(i);
        host_b[i] = 2.0f * static_cast<float>(i);
    }

    float *dev_a, *dev_b, *dev_c;
    CUDA_CHECK(cudaMalloc(&dev_a, bytes));
    CUDA_CHECK(cudaMalloc(&dev_b, bytes));
    CUDA_CHECK(cudaMalloc(&dev_c, bytes));
    CUDA_CHECK(cudaMemcpy(dev_a, host_a, bytes, cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(dev_b, host_b, bytes, cudaMemcpyHostToDevice));

    const int block = 256;
    const int grid = (n + block - 1) / block;
    vector_add<<<grid, block>>>(dev_a, dev_b, dev_c, n);
    CUDA_CHECK(cudaGetLastError());
    CUDA_CHECK(cudaMemcpy(host_c, dev_c, bytes, cudaMemcpyDeviceToHost));

    for (int i = 0; i < n; ++i) {
        if (host_c[i] != 3.0f * static_cast<float>(i)) {
            std::fprintf(stderr, "mismatch at %d: %f\n", i, host_c[i]);
            return 1;
        }
    }
    std::printf("vector_add ok: %d elements\n", n);

    CUDA_CHECK(cudaFree(dev_a));
    CUDA_CHECK(cudaFree(dev_b));
    CUDA_CHECK(cudaFree(dev_c));
    std::free(host_a);
    std::free(host_b);
    std::free(host_c);
    return 0;
}
