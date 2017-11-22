#!/usr/bin/python3

import json
import os
import shlex
import subprocess
import sys

SUPPORTED_FLAVORS = {"services", "sshd", "aiohttp", "httpd", "loadbalancer"}


def main():
    criticctl = os.environ.get("CRITICCTL", "criticctl")
    criticctl_argv = [criticctl]
    settings = []

    flavor = sys.argv[1]

    if f"EXTRA_RUN_ARGS_{flavor.upper()}" in os.environ:
        extra_run_args = os.environ[f"EXTRA_RUN_ARGS_{flavor.upper()}"]
    else:
        extra_run_args = os.environ.get("EXTRA_RUN_ARGS", "")
    extra_run_args = shlex.split(extra_run_args)

    if flavor not in SUPPORTED_FLAVORS:
        print("Unsupported flavor: %r" % flavor, file=sys.stderr)
        return 1

    if "VERBOSE" in os.environ:
        criticctl_argv.append("--verbose")
        settings.append("system.is_debugging:%s" % json.dumps(True))
    elif "QUIET" in os.environ:
        criticctl_argv.append("--quiet")

    database_args = [
        f"--database-driver=postgresql",
        f"--database-host={os.environ.get('DATABASE_HOST', 'database')}",
        f"--database-port={os.environ.get('DATABASE_PORT', '5432')}",
        f"--database-wait={os.environ.get('DATABASE_WAIT', '30')}",
        f"--database-username={os.environ.get('DATABASE_USERNAME', 'critic')}",
        f"--database-password={os.environ.get('DATABASE_PASSWORD', 'critic')}",
    ]

    services_args = [
        f"--services-host={os.environ.get('SERVICES_HOST', 'services')}",
        f"--services-port={os.environ.get('SERVICSE_PORT', '9987')}",
        f"--services-wait={os.environ.get('SERVICES_WAIT', '30')}",
    ]

    listen_args = []
    if "LISTEN_HOST" in os.environ:
        listen_args.append(f"--listen-host={os.environ['LISTEN_HOST']}")
    if "LISTEN_PORT" in os.environ:
        listen_args.append(f"--listen-port={os.environ['LISTEN_PORT']}")

    if flavor in ("monolithic", "services"):
        install_flavor = flavor
    else:
        install_flavor = "auxiliary"

    install_args = [f"--flavor={install_flavor}"]
    install_args.extend(database_args)

    if "IS_TESTING" in os.environ:
        install_args.append("--is-testing")

    if os.environ.get("CRITIC_UID"):
        install_args.append(f"--system-uid={os.environ['CRITIC_UID']}")
    if os.environ.get("CRITIC_GID"):
        install_args.append(f"--system-gid={os.environ['CRITIC_GID']}")

    if flavor in ("monolithic", "services"):
        install_args.extend(
            [
                f"--system-hostname={os.environ['SYSTEM_HOSTNAME']}",
                f"--no-create-database",
                f"--no-create-database-user",
                f"--no-dump-database",
            ]
        )
    else:
        install_args.extend(services_args)

    if flavor == "aiohttp":
        settings.append("frontend.access_scheme:%s" % json.dumps("http"))

    subprocess.check_call(criticctl_argv + ["run-task", "install"] + install_args)

    if flavor == "services":
        run_args = ["run-services", "--no-detach", "--force"]
    elif flavor == "sshd":
        run_args = [
            "run-sshd",
            f"--account-name={os.environ.get('ACCOUNT_NAME', 'git')}",
        ] + listen_args
        if "HOST_KEY_ARGS" in os.environ:
            run_args.extend(shlex.split(os.environ["HOST_KEY_ARGS"]))
    elif flavor == "aiohttp":
        run_args = ["run-frontend", "--flavor=aiohttp"] + listen_args
    elif flavor == "httpd":
        server_admin = os.environ.get("SERVER_ADMIN", "Nameless Administrator")
        server_name = os.environ.get("SERVER_NAME", "critic.example.org")
        run_args = [
            "run-httpd",
            f"--server-admin={server_admin}",
            f"--server-name={server_name}",
        ] + listen_args
    elif flavor == "loadbalancer":
        run_args = ["run-loadbalancer"] + listen_args
    else:
        assert False

    os.execv(criticctl, criticctl_argv + run_args + extra_run_args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
