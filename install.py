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
import traceback

if os.getuid() != 0:
    print """
ERROR: This script must be run as root.
"""
    sys.exit(1)

# Python version check is done before imports below so
# that python 2.6/2.5 users can see the error message.
if sys.version_info[0] != 2 or sys.version_info[1] < 7:
    print """\
Unsupported Python version!  Critic requires Python 2.7.x or later,
but not Python 3.x.  This script must be run in the Python interpreter
that will be used to run Critic."""
    sys.exit(2)

import json
import argparse
import installation

parser = argparse.ArgumentParser(description="Critic installation script")

# Uses default values for everything that has a default value (and isn't
# overridden by other command-line arguments) and signals an error for anything
# that doesn't have a default value and isn't set by a command-line argument.
parser.add_argument("--headless", help=argparse.SUPPRESS, action="store_true")

# Sets configuration.base.IS_DEVELOPMENT to True.
parser.add_argument("--is-development", help=argparse.SUPPRESS, action="store_true")

parser.add_argument("--etc-dir", help="directory where the Critic system configuration is stored", action="store")
parser.add_argument("--install-dir", help="directory where the Critic source code is installed", action="store")
parser.add_argument("--data-dir", help="directory where Critic's persistent data files are stored", action="store")
parser.add_argument("--cache-dir", help="directory where Critic's temporary data files are stored", action="store")
parser.add_argument("--git-dir", help="directory where the main Git repositories are stored", action="store")
parser.add_argument("--log-dir", help="directory where Critic's log files are stored", action="store")
parser.add_argument("--run-dir", help="directory where Critic's runtime files are stored", action="store")

parser.add_argument("--system-hostname", help="FQDN of the system", action="store")
parser.add_argument("--system-username", help="name of system user to run as", action="store")
parser.add_argument("--force-create-system-user", help="don't prompt for permission to create a new system user if doesn't exist", action="store_true")
parser.add_argument("--system-email", help="address used as sender of emails", action="store")
parser.add_argument("--system-groupname", help="name of system group to run as", action="store")
parser.add_argument("--force-create-system-group", help="don't prompt for permission to create a new system group if it doesn't exist", action="store_true")

parser.add_argument("--auth-mode", help="user authentication mode", choices=["host", "critic"], action="store")
parser.add_argument("--session-type", help="session type", choices=["httpauth", "cookie"], action="store")

parser.add_argument("--admin-username", help="name of Critic administrator user", action="store")
parser.add_argument("--admin-email", help="email address to Critic administrator user", action="store")
parser.add_argument("--admin-fullname", help="Critic administrator user's full name", action="store")
parser.add_argument("--admin-password", help="Critic administrator user's password", action="store")

for module in installation.modules:
    if hasattr(module, "add_arguments"):
        module.add_arguments("install", parser)

arguments = parser.parse_args()

if os.path.exists(os.path.join(installation.root_dir, ".install.data")):
    print """
ERROR: Found an .install.data file in the directory you're installing from.

This typically means that Critic is already installed on this system, and if so
then the upgrade.py script should be used to upgrade the installation rather than
re-running install.py.
"""
    sys.exit(1)

if arguments.headless:
    installation.input.headless = True

def abort():
    print
    print "ERROR: Installation aborted."
    print

    for module in reversed(installation.modules):
        try:
            if hasattr(module, "undo"):
                module.undo()
        except:
            print >>sys.stderr, "FAILED: %s.undo()" % module.__name__
            traceback.print_exc()

    sys.exit(1)

try:
    try:
        if not installation.prereqs.check(arguments):
            abort()
    except KeyboardInterrupt:
        abort()
    except SystemExit:
        raise
    except:
        print >>sys.stderr, "FAILED: installation.prereqs.check()"
        traceback.print_exc()
        abort()

    git = installation.prereqs.git

    if installation.process.check_output([git, "status", "--porcelain"]).strip():
        print """
ERROR: This Git repository has local modifications.

Installing from a Git repository with local changes is not supported.
Please commit or stash the changes and then try again.
"""
        sys.exit(1)

    sha1 = installation.process.check_output([git, "rev-parse", "HEAD"]).strip()
    data = { "sha1": sha1 }

    for module in installation.modules:
        try:
            if hasattr(module, "prepare") and not module.prepare("install", arguments, data):
                abort()
        except KeyboardInterrupt:
            abort()
        except SystemExit:
            raise
        except:
            print >>sys.stderr, "FAILED: %s.prepare()" % module.__name__
            traceback.print_exc()
            abort()

    print

    with open(os.path.join(installation.root_dir, ".install.data"), "w") as install_data:
        json.dump(data, install_data)

    for module in installation.modules:
        try:
            if hasattr(module, "install") and not module.install(data):
                abort()
        except KeyboardInterrupt:
            abort()
        except SystemExit:
            raise
        except:
            print >>sys.stderr, "FAILED: %s.execute()" % module.__name__
            traceback.print_exc()
            abort()

    for module in installation.modules:
        try:
            if hasattr(module, "finish"):
                module.finish()
        except:
            print >>sys.stderr, "WARNING: %s.finish() failed" % module.__name__
            traceback.print_exc()

    print "Cleaning up .pyc files owned by root ..."
    for root, _, files in os.walk(installation.root_dir):
        for file in files:
            file = os.path.join(root, file)
            if file.endswith(".pyc") and os.stat(file).st_uid == 0:
                os.unlink(file)

    print
    print "SUCCESS: Installation complete!"
    print
except SystemExit:
    raise
except:
    traceback.print_exc()
    abort()
