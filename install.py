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
import stat
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

if sys.flags.optimize > 0:
    print """
ERROR: Please run this script without -O or -OO options.
"""
    sys.exit(1)

# To avoid accidentally creating files owned by root.
sys.dont_write_bytecode = True

import json
import argparse
import installation

parser = argparse.ArgumentParser(description="Critic installation script")

# Uses default values for everything that has a default value (and isn't
# overridden by other command-line arguments) and signals an error for anything
# that doesn't have a default value and isn't set by a command-line argument.
parser.add_argument("--headless", help=argparse.SUPPRESS, action="store_true")

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

parser.add_argument("--admin-username", help="name of Critic administrator user", action="store")
parser.add_argument("--admin-email", help="email address to Critic administrator user", action="store")
parser.add_argument("--admin-fullname", help="Critic administrator user's full name", action="store")
parser.add_argument("--admin-password", help="Critic administrator user's password", action="store")

for module in installation.modules:
    if hasattr(module, "add_arguments"):
        module.add_arguments("install", parser)

arguments = parser.parse_args()

if os.path.exists(os.path.join(installation.root_dir, ".installed")):
    print """
ERROR: Found an .installed file in the directory you're installing from.

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

    # for module in reversed(installation.modules):
    #     try:
    #         if hasattr(module, "undo"):
    #             module.undo()
    #     except:
    #         print >>sys.stderr, "FAILED: %s.undo()" % module.__name__
    #         traceback.print_exc()

    sys.exit(1)

try:
    try:
        if not installation.prereqs.check("install", arguments):
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

    if installation.utils.run_git([git, "status", "--porcelain"],
                                  cwd=installation.root_dir).strip():
        print """
ERROR: This Git repository has local modifications.

Installing from a Git repository with local changes is not supported.
Please commit or stash the changes and then try again.
"""
        sys.exit(1)

    sha1 = installation.utils.run_git([git, "rev-parse", "HEAD"],
                                      cwd=installation.root_dir).strip()
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

    installed_file = os.path.join(installation.root_dir, ".installed")
    with open(installed_file, "w"):
        pass
    install_py_stat = os.stat(os.path.join(installation.root_dir, "install.py"))
    os.chown(installed_file, install_py_stat.st_uid, install_py_stat.st_gid)

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

    install_data_path = os.path.join(installation.paths.install_dir, ".install.data")
    with open(install_data_path, "w") as install_data_file:
        json.dump(data, install_data_file)
    # May contain SMTP password etc.
    os.chmod(install_data_path, 0600)

    for module in installation.modules:
        try:
            if hasattr(module, "finish"):
                module.finish()
        except:
            print >>sys.stderr, "WARNING: %s.finish() failed" % module.__name__
            traceback.print_exc()

    installation.utils.clean_root_pyc_files()

    print
    print "SUCCESS: Installation complete!"
    print
except SystemExit:
    raise
except:
    traceback.print_exc()
    abort()
