#!/bin/bash
set -e

make \
  docker="sudo docker" \
  apt_proxy=${APT_PROXY:-disable} \
  flavor=${FLAVOR:-default} \
  legacy-upgrade

sudo \
  REPOSITORIES=/home/jl/temporary/critic-review.org/git \
  LEGACY=/home/jl/temporary/critic-review.org/snapshot \
  CRITIC_UID=${CRITIC_UID} \
  CRITIC_GID=${CRITIC_GID} \
  ~/.venv/docker/bin/docker-compose \
    -f docker-compose.yaml \
    -f legacy-upgrade.yaml \
    up legacy-upgrade
