# deepgent jp6 cross-compile toolchain container (linux/arm64).
# All versions arrive as build args resolved from versions.toml; nothing here
# hardcodes a version string.
ARG L4T_CONTAINER
FROM nvcr.io/nvidia/l4t-jetpack:${L4T_CONTAINER}

LABEL org.opencontainers.image.title="deepgent jp6 toolchain" \
      org.opencontainers.image.source="https://github.com/Sherin-SEF-AI/deepgent"

ENV PATH=/usr/local/cuda/bin:${PATH}

WORKDIR /workspace
