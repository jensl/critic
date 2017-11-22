import argparse
import grp
import multiprocessing
import os
import pwd


def parse_arguments(root_dir: str) -> argparse.Namespace:
    from . import Database

    username = pwd.getpwuid(os.geteuid()).pw_name

    parser = argparse.ArgumentParser(
        "python quickstart.py",
        description="Critic instance quick-start utility script.",
    )

    output_group = parser.add_argument_group(
        "Output options"
    ).add_mutually_exclusive_group()
    output_group.add_argument(
        "--quiet", action="store_true", help="Suppress most output"
    )
    output_group.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output and set configuration.debug.IS_DEBUGGING=True",
    )

    parser.add_argument(
        "--testing",
        nargs="?",
        choices=("manual", "automatic"),
        const="manual",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--system-recipient", action="append", default=[], help=argparse.SUPPRESS
    )

    basic_group = parser.add_argument_group("Basic settings")
    basic_group.add_argument(
        "--state-dir", "-s", help="State directory [default=temporary dir]"
    )
    basic_group.add_argument(
        "--open-in-browser",
        action="store_const",
        dest="open_in_browser",
        const=True,
        help="Open Critic's web UI in default web browser",
    )
    basic_group.add_argument(
        "--no-open-in-browser",
        action="store_const",
        dest="open_in_browser",
        const=False,
        help="Do not open Critic's web UI in default web browser",
    )
    basic_group.add_argument(
        "--follow-logs",
        "-f",
        metavar="PATTERN",
        help="Do the equivalent of 'tail -f' on matching log files.",
    )

    Database.setup(parser)

    frontend_group = parser.add_argument_group("HTTP front-end settings")
    frontend_group.add_argument(
        "--http-flavor",
        choices=("wsgiref", "aiohttp"),
        default="aiohttp",
        help="Type of HTTP server to run [default=wsgiref]",
    )
    frontend_group.add_argument(
        "--http-host",
        default="localhost",
        help="Hostname the HTTP server listens at [default=ANY]",
    )
    frontend_group.add_argument(
        "--http-port",
        "-p",
        default=8080,
        type=int,
        help="Port the HTTP server listens at [default=8080]",
    )
    frontend_group.add_argument(
        "--http-lb-frontend",
        choices=("builtin",),
        help="Type of load balancer front-end to start.",
    )
    frontend_group.add_argument(
        "--http-lb-backends",
        type=int,
        default=min(4, multiprocessing.cpu_count()),
        help="Number of back-end processes to start.",
    )
    frontend_group.add_argument(
        "--http-profile",
        action="store_true",
        help="Enable profiling in HTTP server processes.",
    )

    services_group = parser.add_argument_group("Background services")
    services_group.add_argument(
        "--worker-processes",
        type=int,
        default=min(4, multiprocessing.cpu_count()),
        help="Number of worker processes to start.",
    )

    # advanced_group = parser.add_argument_group("Advanced settings")
    # advanced_group.add_argument(
    #     "--cgroup", help="Name of PIDS cgroup to add process to"
    # )

    ui_group = parser.add_argument_group("UI options").add_mutually_exclusive_group()
    ui_group.add_argument(
        "--build-ui",
        action="store_true",
        help="Build (if necessary) the React.js UI. Requires `npm`.",
    )
    ui_group.add_argument(
        "--download-ui",
        action="store_true",
        help="Download pre-built React.js UI from cloud storage.",
    )
    ui_group.add_argument(
        "--start-ui",
        type=int,
        metavar="PORT",
        help=(
            "Start development version of the React.js UI. This will run on a "
            "different port than the backend."
        ),
    )

    admin_group = parser.add_argument_group("Administrator user")
    admin_group.add_argument(
        "--no-admin-user", action="store_true", help=argparse.SUPPRESS
    )
    admin_group.add_argument(
        "--admin-username", default=username, help=argparse.SUPPRESS
    )
    admin_group.add_argument(
        "--admin-fullname", default=username, help=argparse.SUPPRESS
    )
    admin_group.add_argument(
        "--admin-email", default=username + "@localhost", help=argparse.SUPPRESS
    )
    admin_group.add_argument("--admin-password", default="1234", help=argparse.SUPPRESS)

    smtp_group = parser.add_argument_group("Mail delivery")
    smtp_group.add_argument(
        "--enable-maildelivery",
        action="store_true",
        help="Enable delivery of mail to configured SMTP server",
    )
    smtp_group.add_argument(
        "--smtp-host",
        default="localhost",
        help="Hostname of SMTP server to use [default=localhost]",
    )
    smtp_group.add_argument(
        "--smtp-port",
        default=25,
        type=int,
        help="Port of SMTP server to use [default=25]",
    )
    smtp_group.add_argument("--smtp-username", help="SMTP username [default=none]")
    smtp_group.add_argument("--smtp-password", help="SMTP password [default=none]")

    extensions_group = parser.add_argument_group("Extensions support")
    extensions_group.add_argument(
        "--enable-extensions",
        action="store_true",
        help='Enable extension support ("native" extensions only)',
    )
    extensions_group.add_argument(
        "--system-extensions-dir", help="Path of directory containing system extensions"
    )

    parser.add_argument(
        "--use-uwsgi", action="store_true", help="Use uWSGI instead of wsgiref"
    )

    parser.set_defaults(
        mode="quickstart",
        identity="main",
        system_username=pwd.getpwuid(os.geteuid()).pw_name,
        system_groupname=grp.getgrgid(os.getegid()).gr_name,
        coverage_dir=None,
        headless=False,
        pip_extra_arg=[],
        root_dir=root_dir,
    )

    return parser.parse_args()
