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
import json
import pwd
import grp
import py_compile
import argparse

import installation

auth_mode = "host"
session_type = None
allow_anonymous_user = None
access_scheme = None
repository_url_types = ["http"]

password_hash_schemes = ["pbkdf2_sha256", "bcrypt"]
default_password_hash_scheme = "pbkdf2_sha256"
minimum_password_hash_time = 0.25
minimum_rounds = {}

is_development = False
coverage_dir = None

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

        hash_time = time.time() - before

        if hash_time >= minimum_password_hash_time:
            break

        factor = min(1.2, minimum_password_hash_time / hash_time)
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
    if mode == "install":
        parser.add_argument(
            "--auth-mode", choices=["host", "critic"],
            help="user authentication mode")
        parser.add_argument(
            "--session-type", choices=["httpauth", "cookie"],
            help="session type")
        parser.add_argument(
            "--allow-anonymous-user", dest="anonymous", action="store_const",
            const=True, help="allow limited unauthenticated access")
        parser.add_argument(
            "--no-allow-anonymous-user", dest="anonymous", action="store_const",
            const=False, help="do not allow unauthenticated access")
        parser.add_argument(
            "--access-scheme", choices=["http", "https", "both"],
            help="scheme used to access Critic")
        parser.add_argument(
            "--repository-url-types", default="http",
            help=("comma-separated list of supported repository URL types "
                  "(valid types: git, http, ssh and host)"))

    parser.add_argument(
        "--minimum-password-hash-time",
        help="approximate minimum time to spend hashing a single password")

    # Using argparse.SUPPRESS to not include these in --help output; they are
    # not something a typical installer ought to want to use.
    parser.add_argument(
        "--is-development", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--coverage-dir", help=argparse.SUPPRESS)

default_encodings = ["utf-8", "latin-1"]

def prepare(mode, arguments, data):
    global auth_mode, session_type, allow_anonymous_user, access_scheme
    global repository_url_types, default_encodings
    global password_hash_schemes, default_password_hash_scheme
    global minimum_password_hash_time, minimum_rounds
    global is_development, coverage_dir

    header_printed = False

    if arguments.minimum_password_hash_time is not None:
        try:
            minimum_password_hash_time = float(arguments.minimum_password_hash_time)
        except ValueError:
            print ("Invalid --minimum-password-hash-time argument: %s (must be a number)."
                   % arguments.minimum_password_hash_time)
            return False

    if mode == "install":
        if arguments.repository_url_types:
            repository_url_types = filter(
                None, arguments.repository_url_types.split(","))
            invalid_url_types = []
            for url_type in repository_url_types:
                if url_type not in ["git", "http", "ssh", "host"]:
                    invalid_url_types.append(url_type)
            if invalid_url_types or not repository_url_types:
                print ("Invalid --repository-url-types argument: %s"
                       % arguments.repository_url_types)
                if invalid_url_types:
                    print ("These types are invalid: %s"
                           % ",".join(invalid_url_types))
                if not repository_url_types:
                    print "No URL types specified!"
                return False

        if installation.prereqs.passlib_available:
            def check_auth_mode(value):
                if value.strip() not in ("host", "critic"):
                    return "must be one of 'host' and 'critic'"

            if arguments.auth_mode:
                error = check_auth_mode(arguments.auth_mode)
                if error:
                    print "Invalid --auth-mode argument: %s." % arguments.auth_mode
                    return False
                auth_mode = arguments.auth_mode
            else:
                header_printed = True

                print """
Critic Installation: Authentication
===================================

Critic needs to identify (via HTTP authentication) users who access
the Web front-end.  This can be handled in two different ways:

  host    The Web server (Apache) handles authentication and Critic
          only makes use of the user name that it reports via the
          WSGI API.

  critic  Critic implements HTTP authentication itself using passwords
          stored (encrypted) in its database.
"""

                auth_mode = installation.input.string(
                    "Which authentication mode should be used?",
                    default="critic", check=check_auth_mode)

        is_development = arguments.is_development
        coverage_dir = arguments.coverage_dir
    else:
        import configuration

        auth_mode = configuration.base.AUTHENTICATION_MODE

        try: session_type = configuration.base.SESSION_TYPE
        except AttributeError: pass

        try: allow_anonymous_user = configuration.base.ALLOW_ANONYMOUS_USER
        except AttributeError: pass

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

        try: is_development = configuration.debug.IS_DEVELOPMENT
        except AttributeError:
            # Was moved from configuration.base to configuration.debug.
            try: is_development = configuration.base.IS_DEVELOPMENT
            except AttributeError: pass

        try: coverage_dir = configuration.debug.COVERAGE_DIR
        except AttributeError: pass

    if auth_mode == "critic":
        if session_type is None:
            def check_session_type(value):
                if value.strip() not in ("httpauth", "cookie"):
                    return "must be one of 'http' and 'cookie'"

            if mode == "install" and arguments.session_type:
                error = check_session_type(arguments.session_type)
                if error:
                    print "Invalid --session_type argument: %s." % arguments.session_type
                    return False
                session_type = arguments.session_type
            else:
                if not header_printed:
                    header_printed = True
                    print """
Critic Installation: Authentication
==================================="""

                print """
Critic can authenticate users either via HTTP authentication or via a
"Sign in" form and session cookies.  The major difference is that HTTP
authentication requires a valid login to access any page whereas the
other type of authentication supports limited anonymous access.

  httpauth  Use HTTP authentication.

  cookie    Use session cookie based authentication.
"""

                session_type = installation.input.string(
                    "Which session type should be used?",
                    default="cookie", check=check_session_type)

        if allow_anonymous_user is None:
            if session_type == "httpauth":
                allow_anonymous_user = False
            elif mode == "install" and arguments.anonymous is not None:
                allow_anonymous_user = arguments.anonymous
            else:
                if not header_printed:
                    header_printed = True
                    print """
Critic Installation: Authentication
==================================="""

                print """
With cookie based authentication, Critic can support anonymous access.
Users still have to sign in in order to make any changes (such as
write comments in reviews) but will be able to view most information
in the system without signin in.
"""

                allow_anonymous_user = installation.input.yes_or_no(
                    "Do you want to allow anonymous access?", default=True)

    else:
        session_type = "cookie"

    if access_scheme is None:
        if mode == "install" and arguments.access_scheme:
            access_scheme = arguments.access_scheme
        else:
            print """
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
to HTTPS, to avoid sending credentials over plain text connections."""

            if allow_anonymous_user:
                print """\
Anonymous users will be allowed to access the site over HTTP, though.
If this is not desirable, you should select "https" and configure the
web server to redirect all HTTP accesses to HTTPS.
"""
            else:
                print

            def check_access_scheme(value):
                if value not in ("http", "https", "both"):
                    return "must be one of 'http', 'https' and 'both'"

            access_scheme = installation.input.string(
                "How will Critic be accessed?", default="http",
                check=check_access_scheme)

    data["installation.config.auth_mode"] = auth_mode
    data["installation.config.session_type"] = session_type
    data["installation.config.allow_anonymous_user"] = allow_anonymous_user
    data["installation.config.access_scheme"] = access_scheme
    data["installation.config.repository_url_types"] = repository_url_types
    data["installation.config.default_encodings"] = default_encodings

    calibrate_minimum_rounds()

    data["installation.config.password_hash_schemes"] = password_hash_schemes
    data["installation.config.default_password_hash_scheme"] = default_password_hash_scheme
    data["installation.config.minimum_password_hash_time"] = minimum_password_hash_time
    data["installation.config.minimum_rounds"] = minimum_rounds

    data["installation.config.is_development"] = is_development
    data["installation.config.coverage_dir"] = coverage_dir

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
        print """
ERROR: Failed to compile %s:\n%s
""" % (filename, error)
        return False
    else:
        created_file.append(path + "c")
        return True

def install(data):
    source_dir = os.path.join(installation.root_dir, "installation", "templates", "configuration")
    target_dir = os.path.join(installation.paths.etc_dir, "main", "configuration")
    compilation_failed = False

    os.mkdir(target_dir, 0750)
    created_dir.append(target_dir)

    os.chown(target_dir, installation.system.uid, installation.system.gid)

    for entry in os.listdir(source_dir):
        if entry.endswith(".py"):
            source_path = os.path.join(source_dir, entry)
            target_path = os.path.join(target_dir, entry)

            with open(target_path, "w") as target:
                created_file.append(target_path)

                if entry in ("database.py", "smtp.py"):
                    # May contain secrets (passwords.)
                    mode = 0600
                else:
                    # Won't contain secrets.
                    mode = 0640

                os.chmod(target_path, mode)
                os.chown(target_path, installation.system.uid, installation.system.gid)

                with open(source_path, "r") as source:
                    target.write((source.read().decode("utf-8") % data).encode("utf-8"))

            path = os.path.join("configuration", entry)
            if not compile_file(path):
                compilation_failed = True

            os.chmod(target_path + "c", mode)

    if compilation_failed:
        return False

    # Make the newly written 'configuration' module available to the rest of the
    # installation script(s).
    sys.path.insert(0, os.path.join(installation.paths.etc_dir, "main"))

    return True

def upgrade(arguments, data):
    global modified_files

    import configuration

    source_dir = os.path.join(installation.root_dir, "installation", "templates", "configuration")
    target_dir = os.path.join(data["installation.paths.etc_dir"], arguments.identity, "configuration")
    compilation_failed = False

    system_uid = pwd.getpwnam(data["installation.system.username"]).pw_uid
    system_gid = grp.getgrnam(data["installation.system.groupname"]).gr_gid

    no_changes = True

    for entry in os.listdir(source_dir):
        source_path = os.path.join(source_dir, entry)
        target_path = os.path.join(target_dir, entry)
        backup_path = os.path.join(target_dir, "_" + entry)

        source = open(source_path, "r").read().decode("utf-8") % data

        if not os.path.isfile(target_path):
            write_target = True
            no_changes = False
        else:
            if open(target_path).read().decode("utf-8") == source: continue

            no_changes = False

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
            print "Updated file: %s" % target_path

            if not arguments.dry_run:
                if os.path.isfile(target_path):
                    os.rename(target_path, backup_path)
                    renamed.append((target_path, backup_path))

                with open(target_path, "w") as target:
                    created_file.append(target_path)
                    if entry in ("database.py", "smtp.py"):
                        # May contain secrets (passwords.)
                        mode = 0600
                    else:
                        # Won't contain secrets.
                        mode = 0640
                    os.chmod(target_path, mode)
                    os.chown(target_path, system_uid, system_gid)
                    target.write(source.encode("utf-8"))

                path = os.path.join("configuration", entry)
                if not compile_file(path):
                    compilation_failed = True
                else:
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

                os.chmod(target_path + "c", mode)

            modified_files += 1

    if compilation_failed:
        return False

    if no_changes:
        print "No changed configuration files."

    if modified_files:
        reload(configuration)

    return True

def undo():
    map(os.unlink, reversed(created_file))
    map(os.rmdir, reversed(created_dir))

    for target, backup in renamed: os.rename(backup, target)

def finish():
    for target, backup in renamed: os.unlink(backup)
