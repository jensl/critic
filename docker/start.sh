#!/bin/bash
set -e

make \
  -C $(dirname $0) \
  docker="sudo docker" \
  apt_proxy=${APT_PROXY:-disable} \
  flavor=${FLAVOR:-default} \
  postgresql single httpd sshd

env \
  VERSION=${FLAVOR} \
  CRITIC_UID=${CRITIC_UID} \
  CRITIC_GID=${CRITIC_GID} \
  ${DOCKER_COMPOSE:-docker-compose} \
    -f $(dirname $0)/docker-compose.yaml \
    up ${CONTAINERS:-database services api httpd sshd}
