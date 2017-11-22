# Docker

[Docker][docker] is "the world's leading software containerization platform."

Critic can be installed, tested and eventually deployed using Docker. Images can
be built from a clone of Critic's Git repository, or downloaded from the [Docker
Hub][dockerhub].

When running containerized, Critic will be split into one container per system
"component". System components include

* PostgreSQL database
* Background services
* API backends
* HTTP front-end
* SSH server (optional)

## PostgreSQL database

The docker image is based on the PostgreSQL Alpine Linux image, with just a
simple database initialization script added. This script creates a database and
a database user both named "critic". (Note: It does not create any tables.)

It's also entirely possible to run Critic against an "external" PostgreSQL
database, simply by pointing it to the appropriate host. In this case, the basic
database setup needs to be performed manually, however.

## Background services

This component hosts the Git repositories and runs the background services. The
"gateway" service will listen at port 9987 (by default), to which other
components will connect to talk to other background service, and e.g. to access
the Git repositories.

Since the Git repositories should be persistent, the container running this
component should typically be created with a volume containing the Git
repositories.

## API backends

This component runs an HTTP server that handles all dynamic requests, such as
user authentication, the JSON API, and e.g. Git repository access over HTTP.
This component can be scaled to run in multiple containers.

## HTTP front-end

This component runs a "real" HTTP server that handles static resources (e.g. the
UI scripts and stylesheets) and acts as a reverse proxy in front of the API
backends. An image is available that runs Apache for this purpose.

## SSH server (optional)

This component runs an OpenSSH server that authenticates users using SSH public
keys they add via the web UI, and allows access to Git repositories. Note that
the container running this server does not need to have the Git repositories
available; accesses the repositories via a tunnel to the background services.

[docker]: https://www.docker.com/
[dockerhub]: https://hub.docker.com/u/critic/
