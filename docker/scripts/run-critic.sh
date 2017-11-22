#!/bin/bash
set -e

CRITICCTL=${CRITICCTL:-criticctl}
FLAVOR=${FLAVOR:-$1}

DATABASE_ARGS="\
  --database-driver=postgresql \
  --database-host=${DATABASE_HOST:-database} \
  --database-port=${DATABASE_PORT:-5432} \
  --database-wait=${DATABASE_WAIT:-30} \
  --database-username=${DATABASE_USERNAME:-critic} \
  --database-password=${DATABASE_PASSWORD:-critic}"

SERVICES_ARGS="\
  --services-host=${SERVICES_HOST:-services} \
  --services-port=${SERVICSE_PORT:-9987} \
  --services-wait=${SERVICES_WAIT:-30}"

if [[ -v LISTEN_HOST ]]; then
  LISTEN_HOST_ARG="--listen-host=${LISTEN_HOST}"
fi
if [[ -v LISTEN_PORT ]]; then
  LISTEN_PORT_ARG="--listen-port=${LISTEN_PORT}"
fi

case ${FLAVOR} in
  services)
    # Install or upgrade Critic, if not installed already.
    ${CRITICCTL} --verbose run-task install \
      --flavor=services \
      --system-hostname=${SYSTEM_HOSTNAME} \
      ${DATABASE_ARGS} \
      --no-create-database \
      --no-create-database-user

    ${CRITICCTL} --verbose settings set \
      'system.is_debugging:true'

    # Run the services in "foreground" mode.
    exec ${CRITICCTL} --verbose run-services \
      --no-detach \
      --force
    ;;

  aiohttp)
    # Install or upgrade Critic, if not installed already.
    ${CRITICCTL} --verbose run-task install \
      --flavor=api \
      ${DATABASE_ARGS} \
      ${SERVICES_ARGS}

    ${CRITICCTL} --verbose settings set \
      'frontend.access_scheme:"http"'

    # Run aiohttp-based application container.
    exec ${CRITICCTL} --verbose run-frontend \
      --flavor=aiohttp \
      ${LISTEN_HOST_ARG} \
      ${LISTEN_PORT_ARG}
    ;;

  sshd)
    # Install or upgrade Critic, if not installed already.
    ${CRITICCTL} --verbose run-task install \
      --flavor=sshd \
      --system-username=git \
      --system-groupname=git \
      ${DATABASE_ARGS} \
      ${SERVICES_ARGS}

    # Run SSH access service.
    exec ${CRITICCTL} --verbose run-sshd \
      ${LISTEN_PORT_ARG} \
      ${HOST_KEY_ARGS}
    ;;

esac

echo "Invalid FLAVOR: ${FLAVOR:-(undefined)}"
exit 1
