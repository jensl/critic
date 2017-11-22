#!/bin/bash
set -e

wait-for-it                                                                    \
    -h ${DATABASE_HOST:-database}                                              \
    -p ${DATABASE_PORT:-5432}

echo "*:*:*:*:${DATABASE_PASSWORD:-critic}" > ~/.pgpass
chmod 400 ~/.pgpass

pg_restore                                                                     \
    -h ${DATABASE_HOST:-database}                                              \
    -p ${DATABASE_PORT:-5432}                                                  \
    -d ${DATABASE_NAME:-critic}                                                \
    -U ${DATABASE_USERNAME:-critic}                                            \
    -n public                                                                  \
    /legacy/criticdb.dump

mkdir /etc/critic
(
    cd /etc/critic
    tar xzf /legacy/etc_critic.tar.gz
)

${CRITICCTL}                                                                   \
    --verbose                                                                  \
    run-task upgrade                                                           \
    --database-host=${DATABASE_HOST:-database}                                 \
    --database-port=${DATABASE_PORT:-5432}                                     \
    --database-username=${DATABASE_USERNAME:-critic}                           \
    --database-password=${DATABASE_PASSWORD:-critic}                           \
    --no-dump-database

GATEWAY_SECRET=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 32 | head -n 1)

${CRITICCTL}                                                                   \
    --verbose                                                                  \
    settings set                                                               \
    frontend.access_scheme:\"http\"                                            \
    services.gateway.enabled:true                                              \
    services.gateway.secret:\"${GATEWAY_SECRET}\"
