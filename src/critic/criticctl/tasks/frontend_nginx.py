# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2017 the Critic contributors, Opera Software ASA
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License.  You may obtain a copy of
# the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
# License for the specific language governing permissions and limitations under
# the License.

import distutils
import json
import logging
import mimetypes
import os
import tempfile

logger = logging.getLogger(__name__)

UWSGI_CONTAINER = """

    location / {
        uwsgi_pass unix://%(sockets_dir)s/uwsgi.unix;
        include uwsgi_params;
    }

"""

AIOHTTP_CONTAINER = """

    location / {
        proxy_pass http://unix://%(sockets_dir)s/aiohttp_container.unix;
    }

"""

STATIC_RESOURCES = """

    location /static-resource/ {
        alias %(resources_dir)s/;
        expires 30d;

        types {
            %(mimetype_css)s css;
            %(mimetype_js)s js;
            %(mimetype_png)s png;
        }
    }

"""

SSL_SETTINGS = """

    ssl_certificate %(ssl_certificate)s;
    ssl_certificate_key %(ssl_certificate_key)s;
    ssl_protocols %(ssl_protocols)s;
    ssl_ciphers %(ssl_ciphers)s;
    ssl_prefer_server_ciphers on;

    # Uncomment this to enable HTST, which is optional, but a good idea if you
    # intend to keep HTTPS enabled on this site.
    #add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";

"""

TEMPLATE_HTTP = """

server {
    listen 80;
    listen [::]:80;

    server_name %(server_names)s;

    %(container)s

    %(static_resources)s
}

"""

TEMPLATE_HTTPS = """

server {
    listen 80;
    listen [::]:80;

    server_name %(server_names)s;

    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;

    server_name %(server_names)s;

    %(ssl_settings)s

    %(container)s

    %(static_resources)s
}

"""

TEMPLATE_BOTH = """

server {
    listen 80;
    listen [::]:80;
    listen 443 ssl;
    listen [::]:443 ssl;

    server_name %(server_names)s;

    %(ssl_settings)s

    %(container)s

    %(static_resources)s
}

"""

name = "frontend:nginx"
description = "Configure nginx as HTTP(S) front-end."


def setup(parser):
    from critic import api

    identity = parser.get_default("configuration")["system.identity"]

    deps_group = parser.add_argument_group("Dependencies")
    deps_group.add_argument(
        "--install-nginx",
        action="store_true",
        help="Install nginx on the system if it is missing.",
    )

    basic_group = parser.add_argument_group("Basic settings")
    basic_group.add_argument(
        "--access-scheme",
        choices=["http", "https", "both"],
        required=True,
        help="Access schemes to configure.",
    )
    basic_group.add_argument(
        "--server-name",
        action="append",
        default=[api.critic.settings().system.hostname],
        help=(
            "Front-end server name, for virtual server identification. Can be"
            "specified multiple times for multiple aliases."
        ),
    )
    basic_group.add_argument(
        "--enable-site", action="store_true", help="Enable the Critic site."
    )
    basic_group.add_argument(
        "--site-file",
        default="/etc/nginx/sites-available/critic-%s" % identity,
        help="Target path for site file.",
    )
    basic_group.add_argument(
        "--enabled-site-link",
        default="/etc/nginx/sites-enabled/critic-%s" % identity,
        help="Target path for symlink to site file that enables the site.",
    )
    basic_group.add_argument(
        "--disable-default-site",
        action="store_true",
        help="Disable the default nginx site, which typically conflicts.",
    )

    ssl_group = parser.add_argument_group(
        "SSL settings",
        description=(
            "See http://nginx.org/en/docs/http/ngx_http_ssl_module.html for "
            "more information on what the different settings do."
        ),
    )
    ssl_group.add_argument(
        "--ssl-certificate", help="Path to SSL certificate chain file."
    )
    ssl_group.add_argument(
        "--ssl-certificate-key", help="Path to SSL certificate private key file."
    )
    ssl_group.add_argument(
        "--ssl-protocols",
        default="TLSv1 TLSv1.1 TLSv1.2",
        help="Supported SSL protocols.",
    )
    ssl_group.add_argument(
        "--ssl-ciphers",
        default="EECDH+AESGCM:EDH+AESGCM:AES256+EECDH:AES256+EDH",
        help=(
            "Supported SSL ciphers. The default is strict and recommended "
            "for security rather than maximum compatibility. If the latter "
            "is important, a more relaxed setting should be used."
        ),
    )

    parser.set_defaults(need_session=True)


async def main(critic, arguments):
    from critic import api

    from . import fail, as_root, install, service

    settings = api.critic.settings()

    nginx_executable = distutils.spawn.find_executable("nginx")
    if not nginx_executable:
        if not arguments.install_nginx:
            fail(
                "Could not find `nginx` executable in $PATH!",
                "Rerun with --install-nginx to attempt to install required "
                "packages automatically.",
            )
        install("nginx")
        nginx_executable = distutils.spawn.find_executable("nginx")
        if not nginx_executable:
            fail("Still could not find `nginx` executable in $PATH!")

    if settings.frontend.container is None:
        fail(
            "No application container configured!",
            "An application container running Critic needs to be configured "
            "before nginx can be correctly configured as a front-end for it.",
            "Run one of `criticctl run-task container:{uwsgi,aiohttp}` to "
            "configure a container.",
        )
    if settings.frontend.container not in ("uwsgi", "aiohttp"):
        fail(
            "Only uWSGI is currently supported as WSGI container together "
            "with an nginx front-end."
        )

    if os.path.exists(arguments.site_file):
        fail("%s: file already exists!" % arguments.site_file)
    directory = os.path.dirname(arguments.site_file)
    if not os.path.isdir(directory):
        fail("%s: no such directory!" % directory)
    if arguments.enable_site:
        if os.path.exists(arguments.enabled_site_link):
            fail("%s: file already exists!" % arguments.enabled_site_link)
        directory = os.path.dirname(arguments.enabled_site_link)
        if not os.path.isdir(directory):
            fail("%s: no such directory!" % directory)

    if arguments.disable_default_site:
        if not os.path.islink("/etc/nginx/sites-enabled/default"):
            fail("No default site found to disable!")

    parameters = {
        "server_names": " ".join(arguments.server_name),
        "sockets_dir": os.path.join(
            arguments.configuration["paths.runtime"], "sockets"
        ),
    }

    if arguments.access_scheme in ("https", "both"):
        if not arguments.ssl_certificate or not arguments.ssl_certificate_key:
            fail(
                "Must specify --ssl-certificate and --ssl-certificate-key "
                "when configuring HTTPS access. Use --access-scheme=http to "
                "configure HTTP only, or dummy values if you want to fix the "
                "certificate configuration manually later."
            )

        parameters["ssl_settings"] = (
            SSL_SETTINGS
            % {
                "ssl_certificate": arguments.ssl_certificate,
                "ssl_certificate_key": arguments.ssl_certificate_key,
                "ssl_protocols": arguments.ssl_protocols,
                "ssl_ciphers": arguments.ssl_ciphers,
            }
        ).strip()

    if settings.frontend.container == "uwsgi":
        parameters["container"] = (UWSGI_CONTAINER % parameters).strip()
    else:
        parameters["container"] = (AIOHTTP_CONTAINER % parameters).strip()

    parameters["static_resources"] = (
        STATIC_RESOURCES
        % {
            "resources_dir": os.path.join(
                arguments.configuration["paths.home"], "resources"
            ),
            "mimetype_css": mimetypes.guess_type("file.css")[0],
            "mimetype_js": mimetypes.guess_type("file.js")[0],
            "mimetype_png": mimetypes.guess_type("file.png")[0],
        }
    ).strip()

    if arguments.access_scheme == "http":
        template = TEMPLATE_HTTP
    elif arguments.access_scheme == "https":
        template = TEMPLATE_HTTPS
    else:
        template = TEMPLATE_BOTH

    site_file_source = (template % parameters).strip()

    with as_root():
        fd, path = tempfile.mkstemp(
            dir=os.path.dirname(os.path.dirname(arguments.site_file))
        )

        with os.fdopen(fd, "w", encoding="utf-8") as site_file:
            print(site_file_source, file=site_file)

        os.rename(path, arguments.site_file)
        logger.info("Created site file: %s", arguments.site_file)

        if arguments.enable_site:
            os.symlink(arguments.site_file, arguments.enabled_site_link)
            logger.info(
                "Enabled site: %s -> %s",
                arguments.enabled_site_link,
                arguments.site_file,
            )

        if arguments.disable_default_site:
            os.unlink("/etc/nginx/sites-enabled/default")

    if arguments.enable_site:
        service("restart", "nginx")

    http_frontend = await api.systemsetting.fetch(critic, "frontend.http_frontend")
    access_scheme = await api.systemsetting.fetch(critic, "frontend.access_scheme")

    async with api.transaction.start(critic) as transaction:
        transaction.setSystemSetting(http_frontend, "nginx")
        transaction.setSystemSetting(access_scheme, arguments.access_scheme)

    logger.info("Updated Critic's system settings:")
    logger.info("  frontend.http_frontend=%s", json.dumps("nginx"))
    logger.info("  frontend.access_scheme=%s", json.dumps(arguments.access_scheme))
