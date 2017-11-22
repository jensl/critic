#!/bin/bash
set -e

env VERSION=latest-dev REPOSITORIES=/home/jl/temporary/critic-review.org \
  ${DOCKER_COMPOSER:-docker-compose} down --volumes
