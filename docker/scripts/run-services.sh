#!/bin/bash
set -e

# Install or upgrade Critic, if not installed already.
home/bin/criticctl --verbose run-task install \
  --flavor=services \
  --system-hostname=${SYSTEM_HOSTNAME} \
  --database-driver=postgresql \
  --database-host=${DATABASE_HOST} \
  --database-port=${DATABASE_PORT:-5432} \
  --database-wait=${DATABASE_WAIT:-30} \
  --database-username=${DATABASE_USERNAME:-critic} \
  --database-password=${DATABASE_PASSWORD:-critic} \
  --no-create-database \
  --no-create-database-user

# Run the services in "foreground" mode.
exec home/bin/criticctl --verbose run-services --no-detach
