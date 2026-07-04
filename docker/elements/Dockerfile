# elementsd from the official Blockstream release binary.
#
# The tarball is verified against Blockstream's published SHA256SUMS. For a stronger
# guarantee, pin ELEMENTS_SHA256 to the known-good hash of the exact release+arch
# (build then fails if the download does not match). Optionally GPG-verify
# SHA256SUMS.asc against Blockstream's release key as a hardening step.
FROM debian:bookworm-slim AS fetch

ARG ELEMENTS_VERSION=23.2.4
ARG ELEMENTS_SHA256=""
ARG TARGETARCH

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp
RUN set -eux; \
    case "${TARGETARCH:-amd64}" in \
        amd64) ARCH="x86_64-linux-gnu" ;; \
        arm64) ARCH="aarch64-linux-gnu" ;; \
        *) echo "unsupported arch: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    tarball="elements-${ELEMENTS_VERSION}-${ARCH}.tar.gz"; \
    base="https://github.com/ElementsProject/elements/releases/download/elements-${ELEMENTS_VERSION}"; \
    wget -q "${base}/${tarball}"; \
    wget -q "${base}/SHA256SUMS"; \
    grep " ${tarball}\$" SHA256SUMS | sha256sum -c -; \
    if [ -n "${ELEMENTS_SHA256}" ]; then \
        echo "${ELEMENTS_SHA256}  ${tarball}" | sha256sum -c -; \
    fi; \
    tar -xzf "${tarball}"; \
    mkdir -p /opt/elements; \
    cp "elements-${ELEMENTS_VERSION}/bin/elementsd" "elements-${ELEMENTS_VERSION}/bin/elements-cli" /opt/elements/

FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=fetch /opt/elements/elementsd /usr/local/bin/elementsd
COPY --from=fetch /opt/elements/elements-cli /usr/local/bin/elements-cli
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
COPY mine.sh /usr/local/bin/mine.sh
RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/mine.sh

ENV ELEMENTS_DATADIR=/data
VOLUME ["/data"]
EXPOSE 7041
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
