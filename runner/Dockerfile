FROM postgres:16
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-yaml less \
 && rm -rf /var/lib/apt/lists/*
ENV PAGER="less -S" PSQL_PAGER="less -S" LANG=C.UTF-8
