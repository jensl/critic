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

import os
import sys

# To avoid accidentally creating files owned by root.
sys.dont_write_bytecode = True

# Python version check is done before imports below so that python
# 2.6/2.5 users can see the error message.
import pythonversion
pythonversion.check()

import argparse
import subprocess
import multiprocessing
import tempfile
import pwd

import installation

parser = argparse.ArgumentParser(description="Critic extension support installation script",
                                 epilog="""\
Critic extension support is activated by simply running (as root):

    # python extend.py

For finer control over the script's operation you can invoke it with one
or more of the action arguments:

  --prereqs, --fetch, --build, --install and --enable

This can for instance be used to build the v8-jsshell executable on a
system where Critic has not been installed.""",
                                 formatter_class=argparse.RawDescriptionHelpFormatter)

# Uses default values for everything that has a default value (and isn't
# overridden by other command-line arguments) and signals an error for anything
# that doesn't have a default value and isn't set by a command-line argument.
parser.add_argument("--headless", help=argparse.SUPPRESS, action="store_true")

class DefaultBinDir:
    pass

basic = parser.add_argument_group("basic options")
basic.add_argument("--etc-dir", help="directory where the Critic system configuration is stored [default=/etc/critic]", action="store", default="/etc/critic")
basic.add_argument("--identity", help="system identity to upgrade [default=main]", action="store", default="main")
basic.add_argument("--bin-dir", help="directory where the extension host executable is installed [default=/usr/lib/critic/$IDENTITY/bin]", action="store", default=DefaultBinDir)
basic.add_argument("--no-compiler-check", help="disable compiler version check", action="store_true")
basic.add_argument("--dry-run", "-n", help="produce output but don't modify the system at all", action="store_true")
basic.add_argument("--libcurl-flavor", help="libcurl flavor (openssl, gnutls or nss) or install", choices=["openssl", "gnutls", "nss"])

actions = parser.add_argument_group("actions")
actions.add_argument("--prereqs", help="(check for and) install prerequisite software", action="store_true")
actions.add_argument("--fetch", help="fetch the extension host source code", action="store_true")
actions.add_argument("--build", help="build the extension host executable", action="store_true")
actions.add_argument("--install", help="install the extension host executable", action="store_true")
actions.add_argument("--enable", help="enable extension support in Critic's configuration", action="store_true")

actions.add_argument("--with-v8-jsshell", help="v8-jsshell repository URL [default=../v8-jsshell.git]", metavar="URL")
actions.add_argument("--with-v8", help="v8 repository URL [default=git://github.com/v8/v8.git]", metavar="URL")

# Useful to speed up repeated building from clean repositories; used
# by the testing framework.
actions.add_argument("--export-v8-dependencies", help=argparse.SUPPRESS)
actions.add_argument("--import-v8-dependencies", help=argparse.SUPPRESS)

arguments = parser.parse_args()

if arguments.headless:
    installation.input.headless = True

import installation

is_root = os.getuid() == 0

prereqs = arguments.prereqs
fetch = arguments.fetch
build = arguments.build
install = arguments.install
enable = arguments.enable

if not any([prereqs, fetch, build, install, enable]) \
        and arguments.export_v8_dependencies is None \
        and arguments.import_v8_dependencies is None:
    prereqs = fetch = build = install = enable = True

libcurl = False

if any([prereqs, install, enable]) and not is_root:
    print """
ERROR: You need to run this script as root.
"""
    sys.exit(1)

git = os.environ.get("GIT", "git")

if install or enable:
    data = installation.utils.read_install_data(arguments)

    if data is not None:
        git = data["installation.prereqs.git"]

        installed_sha1 = data["sha1"]
        current_sha1 = installation.utils.run_git([git, "rev-parse", "HEAD"],
                                                  cwd=installation.root_dir).strip()

        if installed_sha1 != current_sha1:
            print """
ERROR: You should to run upgrade.py to upgrade to the current commit before
       using this script to enable extension support.
"""
            sys.exit(1)

if arguments.bin_dir is DefaultBinDir:
    bin_dir = os.path.join("/usr/lib/critic", arguments.identity, "bin")
else:
    bin_dir = arguments.bin_dir

if "CXX" in os.environ:
    compiler = os.environ["CXX"]

    try:
        subprocess.check_output([compiler, "--help"])
    except OSError as error:
        print """
ERROR: %r (from $CXX) does not appear to be a valid compiler.
""" % compiler
        sys.exit(1)
else:
    compiler = "g++"

def check_libcurl():
    fd, empty_cc = tempfile.mkstemp(".cc")
    os.close(fd)

    try:
        subprocess.check_output([compiler, "-include", "curl/curl.h", "-c", empty_cc, "-o", "/dev/null"],
                                stderr=subprocess.STDOUT)
        return True
    except subprocess.CalledProcessError as error:
        if "curl/curl.h" in error.output:
            return False
        raise
    finally:
        os.unlink(empty_cc)

def missing_packages():
    packages = []

    if not installation.prereqs.find_executable("svn"):
        packages.append("subversion")
    if not installation.prereqs.find_executable("make"):
        packages.append("make")
    if "CXX" not in os.environ and not installation.prereqs.find_executable("g++"):
        packages.append("g++")
    pg_config = installation.prereqs.find_executable("pg_config")
    if pg_config:
        try:
            subprocess.check_output(["pg_config"], stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            # Just installing the PostgreSQL database server might install
            # a dummy pg_config that just outputs an error message.
            pg_config = None
    if not pg_config:
        packages.append("libpq-dev")

    return packages

if prereqs:
    packages = missing_packages()

    if packages:
        installation.prereqs.install_packages(*packages)

    if not check_libcurl():
        if arguments.libcurl_flavor:
            installation.prereqs.install_packages(
                "libcurl4-%s-dev" % arguments.libcurl_flavor)
        else:
            print """
No version of libcurl-dev appears to be install.  There are usually multiple
versions available to install using different libraries (openssl, gnutls or nss)
for secure communication.  If curl is already installed, you probably need to
install a matching version of libcurl-dev.

This script can install any one of them, or build the extension host executable
without URL loading support ("none").

Available choices are: "openssl", "gnutls", "nss"
Also: "none", "abort"
"""

            def check(string):
                if string not in ("openssl", "gnutls", "nss", "none", "abort"):
                    return 'please answer "openssl", "gnutls", "nss", "none" or "abort"'

            choice = installation.input.string("Install libcurl-dev version?", "none")

            if choice in ("openssl", "gnutls", "nss"):
                installation.prereqs.install_packages("libcurl4-%s-dev" % choice)
            elif choice == "abort":
                print """
ERROR: Installation aborted.
"""
                sys.exit(1)

env = os.environ.copy()

if build and not arguments.no_compiler_check:
    version = subprocess.check_output([compiler, "--version"])
    if version.startswith("g++"):
        version = subprocess.check_output([compiler, "-dumpversion"]).strip().split(".")
        if (int(version[0]), int(version[1])) < (4, 7):
            print """
ERROR: GCC version 4.7 or later required to build v8-jsshell.
HINT: Set $CXX to use a different compiler than '%s', or use
  --no-compiler-check to try to build anyway.
""" % compiler
            sys.exit(1)
    else:
        if "clang" in version:
            note_clang = "NOTE: CLang (version 3.2 and earlier) is known not to work.\n"
        else:
            note_clang = ""

        print """
ERROR: GCC (version 4.7 or later) required to build v8-jsshell.
%sHINT: Set $CXX to use a different compiler than '%s', or use
  --no-compiler-check to try to build anyway.
""" % (note_clang, compiler)
        sys.exit(1)

env["compiler"] = compiler
env["v8static"] = "yes"
env["postgresql"] = "yes"

if check_libcurl():
    env["libcurl"] = "yes"

root = os.path.dirname(os.path.abspath(sys.argv[0]))
v8_jsshell = os.path.join(root, "installation/externals/v8-jsshell")

def do_unprivileged_work():
    if is_root:
        stat = os.stat(sys.argv[0])
        os.environ["USER"] = pwd.getpwuid(stat.st_uid).pw_name
        os.environ["HOME"] = pwd.getpwuid(stat.st_uid).pw_dir
        os.setgid(stat.st_gid)
        os.setuid(stat.st_uid)

    if fetch:
        def fetch_submodule(cwd, submodule, url=None):
            subprocess.check_call(
                [git, "submodule", "init", submodule],
                cwd=cwd)
            if url:
                subprocess.check_call(
                    [git, "config", "submodule.%s.url" % submodule, url],
                    cwd=cwd)
            subprocess.check_call(
                [git, "submodule", "update", submodule],
                cwd=cwd)

        fetch_submodule(root, "installation/externals/v8-jsshell",
                        arguments.with_v8_jsshell)
        fetch_submodule(v8_jsshell, "v8", arguments.with_v8)

    if arguments.import_v8_dependencies or arguments.export_v8_dependencies:
        argv = ["make", "v8dependencies"]

        if arguments.import_v8_dependencies:
            argv.append("v8importdepsfrom=" + arguments.import_v8_dependencies)
        if arguments.export_v8_dependencies:
            argv.append("v8exportdepsto=" + arguments.export_v8_dependencies)

        subprocess.check_call(argv, cwd=v8_jsshell)

    if build:
        subprocess.check_call(
            ["make", "-j%d" % multiprocessing.cpu_count()],
            cwd=v8_jsshell, env=env)

def checked_unprivileged_work(result):
    try:
        do_unprivileged_work()
    except:
        result.put(False)
        raise
    else:
        result.put(True)

if fetch or build \
        or arguments.import_v8_dependencies \
        or arguments.export_v8_dependencies:
    if is_root:
        unprivileged_result = multiprocessing.Queue()
        unprivileged = multiprocessing.Process(target=checked_unprivileged_work,
                                               args=(unprivileged_result,))
        unprivileged.start()
        unprivileged.join()

        if not unprivileged_result.get():
            sys.exit(1)
    else:
        do_unprivileged_work()

if install or enable:
    etc_path = os.path.join(arguments.etc_dir, arguments.identity)

    sys.path.insert(0, etc_path)

    import configuration

    executable = configuration.extensions.FLAVORS.get("js/v8", {}).get("executable")

    if not executable or not os.access(executable, os.X_OK):
        executable = os.path.join(bin_dir, "v8-jsshell")

if install:
    if not os.path.isdir(os.path.dirname(executable)):
        os.makedirs(os.path.dirname(executable))

    subprocess.check_call(
        ["install", os.path.join(v8_jsshell, "out", "jsshell"), executable])

if enable and not configuration.extensions.ENABLED:
    try:
        subprocess.check_output(
            ["su", "-s", "/bin/bash",
             "-c", "psql -q -c 'SELECT 1 FROM extensions LIMIT 1'",
             configuration.base.SYSTEM_USER_NAME],
            stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        installation.database.psql_import(
            "installation/data/dbschema.extensions.sql",
            configuration.base.SYSTEM_USER_NAME)

    data = { "installation.system.username": configuration.base.SYSTEM_USER_NAME,
             "installation.system.groupname": configuration.base.SYSTEM_GROUP_NAME,
             "installation.extensions.enabled": True,
             "installation.extensions.critic_v8_jsshell": executable,
             "installation.extensions.default_flavor": "js/v8" }

    installation.system.fetch_uid_gid()

    installation.paths.mkdir(configuration.extensions.INSTALL_DIR)
    installation.paths.mkdir(configuration.extensions.WORKCOPY_DIR)

    compilation_failed = []

    if installation.config.update_file(os.path.join(etc_path, "configuration"),
                                       "extensions.py", data, arguments,
                                       compilation_failed):
        if compilation_failed:
            print
            print "ERROR: Update aborted."
            print

            installation.config.undo()
            sys.exit(1)

        subprocess.check_call(["criticctl", "restart"])
