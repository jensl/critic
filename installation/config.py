# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2012 Jens Lindström, Opera Software ASA
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

import sys
import os
import os.path
import py_compile
import argparse
import multiprocessing

import installation

auth_mode = "host"
session_type = None
allow_anonymous_user = None
web_server_integration = None
access_scheme = None
repository_url_types = ["http"]
allow_user_registration = None
verify_email_addresses = True
archive_review_branches = True

password_hash_schemes = ["pbkdf2_sha256", "bcrypt"]
default_password_hash_scheme = "pbkdf2_sha256"
minimum_password_hash_time = 0.25
minimum_rounds = {}
auth_database = "internal"
enable_access_tokens = True

ldap_url = "ldap://ldap.example.com:389"
ldap_search_base = "dc=example,dc=com"
ldap_create_user = True
ldap_username_attribute = "uid"
ldap_fullname_attribute = "cn"
ldap_email_attribute = "mail"
ldap_cache_max_age = 600

is_development = False
is_testing = False
coverage_dir = None

class Provider(object):
    def __init__(self, name):
        self.name = name
        self.enabled = False
        self.allow_user_registration = False
        self.verify_email_addresses = False
        self.client_id = None
        self.client_secret = None
        self.redirect_uri = None
        self.bypass_createuser = False

    def load(self, settings):
        if self.name not in settings:
            return
        settings = settings[self.name]
        self.enabled = settings.get("enabled", self.enabled)
        self.allow_user_registration = settings.get("allow_user_registration",
                                                    self.allow_user_registration)
        self.verify_email_addresses = settings.get("verify_email_addresses",
                                                   self.verify_email_addresses)
        self.client_id = settings.get("client_id", self.client_id)
        self.client_secret = settings.get("client_secret", self.client_secret)
        self.redirect_uri = settings.get("redirect_uri", self.redirect_uri)
        self.bypass_createuser = settings.get("bypass_createuser",
                                              self.bypass_createuser)

    def readargs(self, arguments):
        def getarg(name, default):
            value = getattr(arguments, name, None)
            if value is None:
                return default
            return value

        self.enabled = getarg(
            "provider_%s_enabled" % self.name, self.enabled)
        self.allow_user_registration = getarg(
            "provider_%s_user_registration" % self.name,
            self.allow_user_registration)
        self.verify_email_addresses = getarg(
            "provider_%s_verify_email_addresses" % self.name,
            self.verify_email_addresses)
        self.client_id = getarg(
            "provider_%s_client_id" % self.name, self.client_id)
        self.client_secret = getarg(
            "provider_%s_client_secret" % self.name, self.client_secret)
        self.redirect_uri = getarg(
            "provider_%s_redirect_uri" % self.name, self.redirect_uri)

    def store(self, data):
        base = "installation.config.provider_%s." % self.name

        data[base + "enabled"] = self.enabled
        data[base + "allow_user_registration"] = self.allow_user_registration
        data[base + "verify_email_addresses"] = self.verify_email_addresses
        data[base + "client_id"] = self.client_id
        data[base + "client_secret"] = self.client_secret
        data[base + "redirect_uri"] = self.redirect_uri
        data[base + "bypass_createuser"] = self.bypass_createuser

    def scrub(self, data):
        base = "installation.config.provider_%s." % self.name

        del data[base + "client_id"]
        del data[base + "client_secret"]

providers = []
default_provider_names = ["github", "google"]

def calibrate_minimum_rounds():
    import time
    import passlib.context

    min_rounds_name = "%s__min_rounds" % default_password_hash_scheme
    min_rounds_value = 100

    while True:
        calibration_context = passlib.context.CryptContext(
            schemes=[default_password_hash_scheme],
            default=default_password_hash_scheme,
            **{ min_rounds_name: min_rounds_value })

        before = time.time()

        calibration_context.encrypt("password")

        # It's possible encryption was fast enough to measure as zero, or some
        # other ridiculously small number.  "Round" it up to at least one
        # millisecond for sanity.
        hash_time = max(0.001, time.time() - before)

        if hash_time >= minimum_password_hash_time:
            break

        # Multiplication factor.  Make it at least 1.2, to ensure we actually
        # ever finish this loop, and at most 10, to ensure we don't over-shoot
        # by too much.
        factor = max(1.2, min(10.0, minimum_password_hash_time / hash_time))

        min_rounds_value = int(factor * min_rounds_value)

    # If we're upgrading and have a current calibrated value, only change it if
    # the new value is significantly higher, indicating that the system's
    # performance has increased, or the hash implementation has gotten faster.
    if default_password_hash_scheme in minimum_rounds:
        current_value = minimum_rounds[default_password_hash_scheme]
        if current_value * 1.5 > min_rounds_value:
            return

    minimum_rounds[default_password_hash_scheme] = min_rounds_value

def add_arguments(mode, parser):
    def H(help_string):
        # Wrapper to hide arguments when upgrading, but still supporting them.
        # Primarily we need to support arguments on upgrade for testing, which
        # might upgrade from a commit that doesn't support an argument, and thus
        # needs to provide the argument when upgrading to the tested commit.
        if mode == "install":
            return help_string
        else:
            return argparse.SUPPRESS

    parser.add_argument(
        "--auth-mode", choices=["host", "critic"],
        help=H("user authentication mode"))
    parser.add_argument(
        "--session-type", choices=["httpauth", "cookie"],
        help=H("session type"))
    parser.add_argument(
        "--allow-anonymous-user", dest="anonymous", action="store_const",
        const=True, help=H("allow limited unauthenticated access"))
    parser.add_argument(
        "--no-allow-anonymous-user", dest="anonymous", action="store_const",
        const=False, help=H("do not allow unauthenticated access"))
    parser.add_argument(
        "--allow-user-registration", dest="user_registration",
        action="store_const", const=True,
        help=H("allow unattended user registration"))
    parser.add_argument(
        "--no-allow-user-registration", dest="user_registration",
        action="store_const", const=False,
        help=H("do not allow unattended user registration"))
    parser.add_argument(
        "--web-server-integration", choices=["apache", "nginx+uwsgi",
                                             "uwsgi", "none"],
        help=H("web server to set up and integrate with"))
    parser.add_argument(
        "--access-scheme", choices=["http", "https", "both"],
        help=H("scheme used to access Critic"))
    parser.add_argument(
        "--repository-url-types", default="http",
        help=H("comma-separated list of supported repository URL types "
               "(valid types: git, http, ssh and host)"))

    for provider_name in default_provider_names:
        if mode == "install":
            group = parser.add_argument_group(
                "'%s' authentication provider" % provider_name)
        else:
            group = parser

        group.add_argument(
            "--provider-%s-enabled" % provider_name, action="store_const",
            const=True, help=H("enable authentication provider"))
        group.add_argument(
            "--provider-%s-disabled" % provider_name, action="store_const",
            const=False, dest="provider_%s_enabled" % provider_name,
            help=H("disable authentication provider"))
        group.add_argument(
            "--provider-%s-user-registration" % provider_name,
            action="store_const", const=True,
            help=H("enable new user registration"))
        group.add_argument(
            "--provider-%s-no-user-registration" % provider_name,
            action="store_const", const=False,
            dest="provider_%s_user_registration" % provider_name,
            help=H("disable new user registration"))
        group.add_argument(
            "--provider-%s-client-id" % provider_name, action="store",
            help=H("OAuth2 client id"))
        group.add_argument(
            "--provider-%s-client-secret" % provider_name, action="store",
            help=H("OAuth2 client secret"))
        group.add_argument(
            "--provider-%s-redirect-uri" % provider_name, action="store",
            help=H("OAuth2 authentication callback URI"))

    parser.add_argument(
        "--minimum-password-hash-time",
        help=H("approximate minimum time to spend hashing a single password"))

    # Using argparse.SUPPRESS to not include these in --help output; they are
    # not something a typical installer ought to want to use.
    parser.add_argument(
        "--is-development", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--is-testing", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--coverage-dir", help=argparse.SUPPRESS)

default_encodings = ["utf-8", "latin-1"]

def prepare(mode, arguments, data):
    global auth_mode, session_type, allow_anonymous_user
    global web_server_integration, access_scheme
    global repository_url_types, default_encodings, allow_user_registration
    global verify_email_addresses, archive_review_branches
    global password_hash_schemes, default_password_hash_scheme
    global minimum_password_hash_time, minimum_rounds, auth_database
    global enable_access_tokens
    global is_development, is_testing, coverage_dir

    global ldap_url, ldap_search_base, ldap_create_user, ldap_username_attribute
    global ldap_fullname_attribute, ldap_email_attribute, ldap_cache_max_age

    header_printed = False

    if mode == "install":
        if arguments.minimum_password_hash_time is not None:
            try:
                minimum_password_hash_time = float(arguments.minimum_password_hash_time)
            except ValueError:
                print(("Invalid --minimum-password-hash-time argument: %s (must be a number)."
                       % arguments.minimum_password_hash_time))
                return False

        if arguments.repository_url_types:
            repository_url_types = filter(
                None, arguments.repository_url_types.split(","))
            invalid_url_types = []
            for url_type in repository_url_types:
                if url_type not in ["git", "http", "ssh", "host"]:
                    invalid_url_types.append(url_type)
            if invalid_url_types or not repository_url_types:
                print(("Invalid --repository-url-types argument: %s"
                       % arguments.repository_url_types))
                if invalid_url_types:
                    print(("These types are invalid: %s"
                           % ",".join(invalid_url_types)))
                if not repository_url_types:
                    print("No URL types specified!")
                return False

        def check_auth_mode(value):
            if value.strip() not in ("host", "critic"):
                return "must be one of 'host' and 'critic'"

        if arguments.auth_mode:
            error = check_auth_mode(arguments.auth_mode)
            if error:
                print("Invalid --auth-mode argument: %s." % arguments.auth_mode)
                return False
            auth_mode = arguments.auth_mode
        else:
            header_printed = True

            print("""
Critic Installation: Authentication
===================================

Critic needs to identify (via HTTP authentication) users who access
the Web front-end.  This can be handled in two different ways:

  host    The Web server (Apache) handles authentication and Critic
          only makes use of the user name that it reports via the
          WSGI API.

  critic  Critic implements HTTP authentication itself using passwords
          stored (encrypted) in its database.
""")

            auth_mode = installation.input.string(
                "Which authentication mode should be used?",
                default="critic", check=check_auth_mode)

        is_development = arguments.is_development
        is_testing = arguments.is_testing
        coverage_dir = arguments.coverage_dir
    else:
        import configuration

        auth_mode = configuration.base.AUTHENTICATION_MODE

        try: session_type = configuration.base.SESSION_TYPE
        except AttributeError: pass

        try: allow_anonymous_user = configuration.base.ALLOW_ANONYMOUS_USER
        except AttributeError: pass

        try: web_server_integration = configuration.base.WEB_SERVER_INTEGRATION
        except AttributeError: web_server_integration = "apache"

        try: access_scheme = configuration.base.ACCESS_SCHEME
        except AttributeError: pass

        try: repository_url_types = configuration.base.REPOSITORY_URL_TYPES
        except AttributeError: pass

        try: default_encodings = configuration.base.DEFAULT_ENCODINGS
        except AttributeError: pass

        try:
            password_hash_schemes = configuration.auth.PASSWORD_HASH_SCHEMES
            default_password_hash_scheme = configuration.auth.DEFAULT_PASSWORD_HASH_SCHEME
            minimum_password_hash_time = configuration.auth.MINIMUM_PASSWORD_HASH_TIME
            minimum_rounds = configuration.auth.MINIMUM_ROUNDS
        except AttributeError:
            pass

        try:
            auth_database = configuration.auth.DATABASE
        except AttributeError:
            pass

        try:
            enable_access_tokens = configuration.auth.ENABLE_ACCESS_TOKENS
        except AttributeError:
            pass

        try: is_development = configuration.debug.IS_DEVELOPMENT
        except AttributeError:
            # Was moved from configuration.base to configuration.debug.
            try: is_development = configuration.base.IS_DEVELOPMENT
            except AttributeError: pass

        try: is_testing = configuration.debug.IS_TESTING
        except AttributeError: is_testing = arguments.is_testing

        try: coverage_dir = configuration.debug.COVERAGE_DIR
        except AttributeError: pass

        try: allow_user_registration = configuration.base.ALLOW_USER_REGISTRATION
        except AttributeError: pass

        try: verify_email_addresses = configuration.base.VERIFY_EMAIL_ADDRESSES
        except AttributeError: pass

        try: archive_review_branches = configuration.base.ARCHIVE_REVIEW_BRANCHES
        except AttributeError: pass

        try:
            ldap = configuration.auth.DATABASES["ldap"]
        except (AttributeError, KeyError):
            pass
        else:
            ldap_url = ldap.get("ldap_url", ldap_url)
            ldap_search_base = ldap.get("ldap_search_base", ldap_search_base)
            ldap_create_user = ldap.get("ldap_create_user", ldap_create_user)
            ldap_username_attribute = ldap.get("ldap_username_attribute",
                                               ldap_username_attribute)
            ldap_fullname_attribute = ldap.get("ldap_fullname_attribute",
                                               ldap_fullname_attribute)
            ldap_email_attribute = ldap.get("ldap_email_attribute",
                                            ldap_email_attribute)
            ldap_cache_max_age = ldap.get("ldap_cache_max_age",
                                          ldap_cache_max_age)

    if auth_mode == "critic":
        if session_type is None:
            def check_session_type(value):
                if value.strip() not in ("httpauth", "cookie"):
                    return "must be one of 'http' and 'cookie'"

            if arguments.session_type:
                error = check_session_type(arguments.session_type)
                if error:
                    print("Invalid --session_type argument: %s." % arguments.session_type)
                    return False
                session_type = arguments.session_type
            else:
                if not header_printed:
                    header_printed = True
                    print("""
Critic Installation: Authentication
===================================""")

                print("""
Critic can authenticate users either via HTTP authentication or via a
"Sign in" form and session cookies.  The major difference is that HTTP
authentication requires a valid login to access any page whereas the
other type of authentication supports limited anonymous access.

  httpauth  Use HTTP authentication.

  cookie    Use session cookie based authentication.
""")

                session_type = installation.input.string(
                    "Which session type should be used?",
                    default="cookie", check=check_session_type)

        if allow_anonymous_user is None:
            if session_type == "httpauth":
                allow_anonymous_user = False
            elif arguments.anonymous is not None:
                allow_anonymous_user = arguments.anonymous
            else:
                if not header_printed:
                    header_printed = True
                    print("""
Critic Installation: Authentication
===================================""")

                print("""
With cookie based authentication, Critic can support anonymous access.
Users still have to sign in in order to make any changes (such as
write comments in reviews) but will be able to view most information
in the system without signin in.
""")

                allow_anonymous_user = installation.input.yes_or_no(
                    "Do you want to allow anonymous access?", default=True)

        if allow_user_registration is None:
            if session_type == "httpauth":
                allow_user_registration = False
            elif arguments.user_registration is not None:
                allow_user_registration = arguments.user_registration
            else:
                if not header_printed:
                    header_printed = True
                    print("""
Critic Installation: Authentication
===================================""")

                print("""
With cookie based authentication, Critic can support unattended user
registration.  With this enabled, the "Sign in" page has a link to a
page where a new user can register a Critic user without needing to
contact the system administrator(s).
""")

                allow_user_registration = installation.input.yes_or_no(
                    "Do you want to allow user registration?", default=False)
    else:
        session_type = "cookie"

    if web_server_integration is None:
        if arguments.web_server_integration:
            web_server_integration = arguments.web_server_integration
        else:
            print("""
Critic Installation: Web Server Integration
===========================================

This installation script can install and do basic configuration of a
few different host web servers.  Supported web servers are:

  1) nginx + uWSGI

     Use the nginx web server together with uWSGI as the WSGI
     application server to actually run Critic.

     This is the recommended option for new installs.

  2) uWSGI

     Use uWSGI as both HTTP(S) front-end and as the WSGI application
     server to actually run Critic.

  3) Apache + mod_wsgi

     Use the Apache web server and its third-party WSGI module
     (mod_wsgi) to actually run Critic.  This is the traditional
     configuration used to run Critic, but mod_wsgi is not actively
     maintained, and has some known issues.

  4) no integration

     Don't configure any web server.  The installation performed by
     this script will be incomplete and the system administrator will
     need to set the integration up themselves.
""")

            def check_web_server_integration(value):
                if value not in ("1", "nginx+uwsgi",
                                 "2", "uwsgi",
                                 "3", "apache",
                                 "4", "none"):
                    return ("must be one of '1'/'nginx+uwsgi', '2'/'uwsgi', "
                            "'3'/'apache' and '4'/'none'")

            web_server_integration = installation.input.string(
                "What web server should be set up?", default="nginx+uwsgi",
                check=check_web_server_integration)

            aliases = { "1": "nginx+uwsgi",
                        "2": "uwsgi",
                        "3": "apache",
                        "4": "none" }

            if web_server_integration in aliases:
                web_server_integration = aliases[web_server_integration]

    if access_scheme is None:
        if arguments.access_scheme:
            access_scheme = arguments.access_scheme
        else:
            print("""
Critic Installation: Scheme
===========================

Critic can be set up to be accessed over HTTP, HTTPS, or both.  This
installation script will not do the actual configuration of the host
web server (Apache) necessary for it to support the desired schemes
(in particular HTTPS, which is non-trivial,) but can at least set up
Critic's Apache site declaration appropriately.

You have three choices:

  http   Critic will be accessible only over HTTP.

  https  Critic will be accessible only over HTTPS.

  both   Critic will be accessible over both HTTP and HTTPS.

If you choose "both", Critic will redirect all authenticated accesses
to HTTPS, to avoid sending credentials over plain text connections.""")

            if allow_anonymous_user:
                print("""\
Anonymous users will be allowed to access the site over HTTP, though.
If this is not desirable, you should select "https" and configure the
web server to redirect all HTTP accesses to HTTPS.
""")
            else:
                print()

            def check_access_scheme(value):
                if value not in ("http", "https", "both"):
                    return "must be one of 'http', 'https' and 'both'"

            access_scheme = installation.input.string(
                "How will Critic be accessed?", default="http",
                check=check_access_scheme)

    if mode == "upgrade" \
           and hasattr(configuration, "auth") \
           and hasattr(configuration.auth, "PROVIDERS"):
        for provider_name in configuration.auth.PROVIDERS:
            provider = Provider(provider_name)
            provider.load(configuration.auth.PROVIDERS)
            providers.append(provider)
    else:
        providers.extend(Provider(provider_name)
                         for provider_name in default_provider_names)

    if access_scheme == "http":
        base_url = "http"
    else:
        base_url = "https"

    base_url += "://%s/oauth/" % installation.system.hostname

    for provider in providers:
        provider.readargs(arguments)
        if provider.redirect_uri is None:
            provider.redirect_uri = base_url + provider.name

    data["installation.config.auth_mode"] = auth_mode
    data["installation.config.session_type"] = session_type
    data["installation.config.allow_anonymous_user"] = allow_anonymous_user
    data["installation.config.web_server_integration"] = web_server_integration
    data["installation.config.access_scheme"] = access_scheme
    data["installation.config.repository_url_types"] = repository_url_types
    data["installation.config.default_encodings"] = default_encodings
    data["installation.config.allow_user_registration"] = allow_user_registration
    data["installation.config.verify_email_addresses"] = verify_email_addresses
    data["installation.config.archive_review_branches"] = archive_review_branches

    data["installation.config.password_hash_schemes"] = password_hash_schemes
    data["installation.config.default_password_hash_scheme"] = default_password_hash_scheme
    data["installation.config.minimum_password_hash_time"] = minimum_password_hash_time
    data["installation.config.auth_database"] = auth_database
    data["installation.config.enable_access_tokens"] = enable_access_tokens

    data["installation.config.is_quickstart"] = False
    data["installation.config.is_development"] = is_development
    data["installation.config.is_testing"] = is_testing
    data["installation.config.coverage_dir"] = coverage_dir

    if mode == "upgrade":
        data["installation.config.highlight.max_workers"] = \
            configuration.services.HIGHLIGHT["max_workers"]
        data["installation.config.changeset.max_workers"] = \
            configuration.services.CHANGESET["max_workers"]
    else:
        cpu_count = multiprocessing.cpu_count()

        data["installation.config.highlight.max_workers"] = cpu_count
        data["installation.config.changeset.max_workers"] = max(1, cpu_count / 2)

    for provider in providers:
        provider.store(data)

    data["installation.config.ldap_url"] = ldap_url
    data["installation.config.ldap_search_base"] = ldap_search_base
    data["installation.config.ldap_create_user"] = ldap_create_user
    data["installation.config.ldap_username_attribute"] = ldap_username_attribute
    data["installation.config.ldap_fullname_attribute"] = ldap_fullname_attribute
    data["installation.config.ldap_email_attribute"] = ldap_email_attribute
    data["installation.config.ldap_cache_max_age"] = ldap_cache_max_age

    return True

created_file = []
created_dir = []
renamed = []
modified_files = 0

def compile_file(filename):
    global created_file
    try:
        path = os.path.join(installation.paths.etc_dir, "main", filename)
        with installation.utils.as_critic_system_user():
            py_compile.compile(path, doraise=True)
    except py_compile.PyCompileError as error:
        print("""
ERROR: Failed to compile %s:\n%s
""" % (filename, error))
        return False
    else:
        created_file.append(path + "c")
        return True

def set_file_mode_and_owner(path):
    uid = installation.system.uid
    gid = installation.system.gid

    filename = os.path.basename(path)
    if filename in ("database.py", "auth.py", "smtp-credentials.json"):
        # May contain sensitive information.
        mode = 0600
        if filename == "smtp-credentials.json":
            uid = gid = 0
    else:
        mode = 0640

    os.chmod(path, mode)

    if not installation.is_quick_start:
        os.chown(path, uid, gid)

def copy_file_mode_and_owner(src_path, dst_path):
    status = os.stat(src_path)

    os.chmod(dst_path, status.st_mode)
    os.chown(dst_path, status.st_uid, status.st_gid)

def install(data):
    if auth_mode == "critic":
        calibrate_minimum_rounds()
    data["installation.config.minimum_rounds"] = minimum_rounds

    source_dir = os.path.join(installation.root_dir, "installation", "templates", "configuration")
    target_dir = os.path.join(installation.paths.etc_dir, "main", "configuration")
    compilation_failed = False

    os.mkdir(target_dir, 0750)
    created_dir.append(target_dir)

    os.chown(target_dir, installation.system.uid, installation.system.gid)

    for entry in os.listdir(source_dir):
        source_path = os.path.join(source_dir, entry)
        target_path = os.path.join(target_dir, entry)

        with open(target_path, "w") as target:
            created_file.append(target_path)

            with open(source_path, "r") as source:
                target.write((source.read().decode("utf-8") % data).encode("utf-8"))

        set_file_mode_and_owner(target_path)

        if entry.endswith(".py"):
            path = os.path.join("configuration", entry)
            if not compile_file(path):
                compilation_failed = True
            else:
                copy_file_mode_and_owner(target_path, target_path + "c")

    if compilation_failed:
        return False

    # Make the newly written 'configuration' module available to the rest of the
    # installation script(s).
    sys.path.insert(0, os.path.join(installation.paths.etc_dir, "main"))

    return True

def update_file(target_dir, entry, data, arguments, compilation_failed):
    global modified_files

    import configuration

    source_dir = os.path.join(installation.root_dir, "installation", "templates", "configuration")
    compilation_failed = False

    source_path = os.path.join(source_dir, entry)
    target_path = os.path.join(target_dir, entry)
    backup_path = os.path.join(target_dir, "_" + entry)

    source = open(source_path, "r").read().decode("utf-8") % data

    if not os.path.isfile(target_path):
        write_target = True
    else:
        if open(target_path).read().decode("utf-8") == source:
            return False

        def generateVersion(label, path):
            if label == "updated":
                with open(path, "w") as target:
                    target.write(source.encode("utf-8"))

        update_query = installation.utils.UpdateModifiedFile(
            arguments,
            message="""\
A configuration file is about to be updated.  Please check that no
local modifications are being overwritten.

Current version: %(current)s
Updated version: %(updated)s

Please note that if any configuration options were added in the
updated version, the system will most likely break if you do not
either install the updated version or manually transfer the new
configuration options to the existing version.
""",
            versions={ "current": target_path,
                       "updated": target_path + ".new" },
            options=[ ("i", "install the updated version"),
                      ("k", "keep the current version"),
                      ("d", ("current", "updated")) ],
            generateVersion=generateVersion)

        write_target = update_query.prompt() == "i"

    if write_target:
        print("Updated file: %s" % target_path)

        if not arguments.dry_run:
            if os.path.isfile(target_path):
                os.rename(target_path, backup_path)
                renamed.append((target_path, backup_path))

            with open(target_path, "w") as target:
                created_file.append(target_path)
                target.write(source.encode("utf-8"))

            set_file_mode_and_owner(target_path)

            if target_path.endswith(".py"):
                path = os.path.join("configuration", entry)
                if not compile_file(path):
                    compilation_failed.append(path)
                else:
                    copy_file_mode_and_owner(target_path, target_path + "c")

                    # The module's name (relative the 'configuration' package)
                    # is the base name minus the trailing ".py".
                    module_name = os.path.basename(target_path)[:-3]

                    if module_name != "__init__" \
                            and hasattr(configuration, module_name):
                        # Reload the updated module so that code executing later
                        # sees added configuration options.  (It will also see
                        # removed configuration options, but that is unlikely to
                        # be a problem.)
                        reload(getattr(configuration, module_name))

        modified_files += 1

    return True

def upgrade(arguments, data):
    global modified_files

    import configuration

    if auth_mode == "critic":
        calibrate_minimum_rounds()
    data["installation.config.minimum_rounds"] = minimum_rounds

    source_dir = os.path.join(installation.root_dir, "installation", "templates", "configuration")
    target_dir = os.path.join(data["installation.paths.etc_dir"], arguments.identity, "configuration")
    compilation_failed = []

    no_changes = True

    for entry in os.listdir(source_dir):
        if update_file(target_dir, entry, data, arguments, compilation_failed):
            no_changes = False

    if compilation_failed:
        return False

    if no_changes:
        print("No changed configuration files.")

    if modified_files:
        reload(configuration)

    return True

def undo():
    map(os.unlink, reversed(created_file))
    map(os.rmdir, reversed(created_dir))

    for target, backup in renamed: os.rename(backup, target)

def finish(mode, arguments, data):
    for target, backup in renamed: os.unlink(backup)

    for provider in providers:
        provider.scrub(data)
