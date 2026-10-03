FROM buildpack-deps:bookworm AS isolate
RUN apt-get update && \
    apt-get install -y --no-install-recommends git libcap-dev && \
    rm -rf /var/lib/apt/lists/* && \
    git clone https://github.com/envicutor/isolate.git /tmp/isolate/ && \
    cd /tmp/isolate && \
    git checkout af6db68042c3aa0ded80787fbb78bc0846ea2114 && \
    make -j$(nproc) install && \
    rm -rf /tmp/*

FROM node:26-bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN dpkg-reconfigure -p critical dash
# Trimmed to what the baked-in C# and Python packages need. Upstream's list
# served dozens of languages and no longer resolves: its buster base is EOL.
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl tar \
    coreutils util-linux libc6-dev binutils build-essential locales rename \
    procps python3 libcap-dev libseccomp-dev libicu72 libssl3 zlib1g && \
    rm -rf /var/lib/apt/lists/*
RUN useradd -M piston
COPY --from=isolate /usr/local/bin/isolate /usr/local/bin
COPY --from=isolate /usr/local/etc/isolate /usr/local/etc/isolate

RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && locale-gen

WORKDIR /piston_api
COPY ["api/package.json", "api/package-lock.json", "./"]
RUN npm install
COPY api/src ./src

# Runtimes are baked in at build time rather than installed through ppman:
# upstream's package index and registry are not ours to depend on.
COPY scripts/install-package.sh /usr/local/bin/install-package
COPY packages/dotnet/10.0.401 /stage/dotnet/10.0.401
COPY packages/python/3.13.16 /stage/python/3.13.16
RUN install-package dotnet 10.0.401 && \
    install-package python 3.13.16 && \
    rm -rf /stage

CMD ["/piston_api/src/docker-entrypoint.sh"]
EXPOSE 2000/tcp
