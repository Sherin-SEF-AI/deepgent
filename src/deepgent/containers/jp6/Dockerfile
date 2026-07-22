# deepgent jp6 cross-compile toolchain container (linux/arm64).
# All versions arrive as build args resolved from versions.toml; nothing here
# hardcodes a version string.
ARG L4T_CONTAINER
FROM nvcr.io/nvidia/l4t-jetpack:${L4T_CONTAINER}

LABEL org.opencontainers.image.title="deepgent jp6 toolchain" \
      org.opencontainers.image.source="https://github.com/Sherin-SEF-AI/deepgent"

ENV PATH=/usr/local/cuda/bin:${PATH}

# Static analysis for misra_gate (section 10): cppcheck ships the MISRA addon
# (rule numbers only; no licensed rule text is bundled or fetched).
RUN apt-get update \
    && apt-get install -y --no-install-recommends clang-tidy cppcheck \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
