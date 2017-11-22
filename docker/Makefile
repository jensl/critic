docker ?= docker
context ?= ..
dev ?= no
apt_proxy ?= disable

ifeq ($(flavor), alpine)
	version := alpine
	flavor_suffix := -alpine
else
	version := latest
endif

ifeq ($(dev), yes)
	dev_suffix := -dev
endif

default_tag := $(version)$(dev_suffix)
tag ?= $(default_tag)

ifeq ($(for_testing), yes)
	docker_build_args += --label for_testing=yes
endif

ifneq ($(apt_proxy), disable)
	docker_build_args += --build-arg apt_get_args="-o Acquire::http::Proxy=$(apt_proxy)"
	docker_build_args += --network=host
endif

all: services sshd aiohttp frontend postgresql httpd extensionhost

base: dockerfiles/Dockerfile.base$(flavor_suffix)$(dev_suffix)
	$(docker) build $(docker_build_args) -t critic/base:$(tag) -f $< $(context)

single: dockerfiles/Dockerfile.single$(flavor_suffix) base ui
	$(docker) build $(docker_build_args) --build-arg base_version=$(tag) -t critic/single:$(tag) -f $< $(context)
	$(docker) tag critic/single:$(tag) critic/services:$(tag)
	$(docker) tag critic/single:$(tag) critic/sshd:$(tag)
	$(docker) tag critic/single:$(tag) critic/aiohttp:$(tag)
	$(docker) tag critic/single:$(tag) critic/frontend:$(tag)

services: dockerfiles/Dockerfile.services$(flavor_suffix)$(dev_suffix) base
	$(docker) build $(docker_build_args) --build-arg base_version=$(tag) -t critic/services:$(tag) -f $< $(context)

sshd: dockerfiles/Dockerfile.sshd$(flavor_suffix)$(dev_suffix) base
	$(docker) build $(docker_build_args) --build-arg base_version=$(tag) -t critic/sshd:$(tag) -f $< $(context)

aiohttp: dockerfiles/Dockerfile.aiohttp$(flavor_suffix) base
	$(docker) build $(docker_build_args) --build-arg base_version=$(tag) -t critic/aiohttp:$(tag) -f $< $(context)

frontend: dockerfiles/Dockerfile.frontend$(flavor_suffix) base
	$(docker) build $(docker_build_args) --build-arg base_version=$(tag) -t critic/frontend:$(tag) -f $< $(context)

postgresql: dockerfiles/Dockerfile.postgresql
	$(docker) build $(docker_build_args) --build-arg version=$(version) -t critic/postgresql:$(tag) -f $< $(context)

ui: dockerfiles/Dockerfile.ui
	$(docker) build $(docker_build_args) -t critic/ui:$(tag) -f $< $(context)

httpd: dockerfiles/Dockerfile.httpd ui
	$(docker) build $(docker_build_args) --build-arg version=$(version) -t critic/httpd:$(tag) -f $< $(context)

extensionhost: dockerfiles/Dockerfile.extensionhost
	$(docker) build $(docker_build_args) --build-arg version=$(version) -t critic/extensionhost:$(tag) -f $< $(context)

legacy-upgrade: dockerfiles/Dockerfile.legacy-upgrade base
	$(docker) build $(docker_build_args) --build-arg base_version=$(tag) -t critic/legacy-upgrade:$(tag) -f $< $(context)
