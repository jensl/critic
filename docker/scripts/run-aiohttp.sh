#!/bin/bash
set -e

# Install or upgrade Critic, if not installed already.
home/bin/criticctl --verbose run-task install \
  --flavor=container \
  --services-host=${SERVICES_HOST} \
  --services-wait=${SERVICES_WAIT:-30} \
  --database-driver=postgresql \
  --database-host=${DATABASE_HOST} \
  --database-port=${DATABASE_PORT:-5432} \
  --database-wait=${DATABASE_WAIT:-30} \
  --database-username=${DATABASE_USERNAME:-critic} \
  --database-password=${DATABASE_PASSWORD:-critic}

# Run the aiohttp application container.
exec home/bin/criticctl --verbose run-frontend \
  --flavor=aiohttp \
  --host=${LISTEN_HOST:\*} \
  --port=${LISTEN_PORT:-8080}
