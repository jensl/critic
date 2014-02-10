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
import json
import traceback
import subprocess

if sys.flags.optimize > 0:
    print """
ERROR: Please run this script without -O or -OO options.
"""
    sys.exit(1)

# To avoid accidentally creating files owned by root.
sys.dont_write_bytecode = True

import argparse

sys.path.insert(0, os.path.join(os.getcwd(), "src"))

import installation

parser = argparse.ArgumentParser(description="Critic upgrade script")

# Uses default values for everything that has a default value (and isn't
# overridden by other command-line arguments) and signals an error for anything
# that doesn't have a default value and isn't set by a command-line argument.
parser.add_argument("--headless", help=argparse.SUPPRESS, action="store_true")

parser.add_argument("--etc-dir", default="/etc/critic", help="directory where the Critic system configuration is stored", action="store")
parser.add_argument("--identity", "-i", default="main", help="system identity to upgrade", action="store")
parser.add_argument("--dry-run", "-n", help="produce output but don't modify the system at all", action="store_true")

for module in installation.modules:
    if hasattr(module, "add_arguments"):
        module.add_arguments("upgrade", parser)

arguments = parser.parse_args()

if arguments.headless:
    installation.input.headless = True

if os.getuid() != 0:
    print """
ERROR: This script must be run as root.
"""
    sys.exit(1)

def abort():
    print
    print "ERROR: Upgrade aborted."
    print

    for module in reversed(installation.modules):
        try:
            if hasattr(module, "undo"):
                module.undo()
        except:
            print >>sys.stderr, "FAILED: %s.undo()" % module.__name__
            traceback.print_exc()

    if installation.initd.servicemanager_stopped and not installation.initd.start():
        print "WARNING: Undo failed to start Critic background services again..."
    if installation.apache.apache_stopped and not installation.apache.start():
        print "WARNING: Undo failed to start Apache again..."

    sys.exit(1)

etc_path = os.path.join(arguments.etc_dir, arguments.identity)

if not os.path.isdir(etc_path):
    print """\
%s: no such directory

Make sure the --etc-dir[=%s] and --identity[=%s] options
correctly define where the installed system's configuration is stored.""" % (etc_path, arguments.etc_dir, arguments.identity)
    sys.exit(1)

sys.path.insert(0, etc_path)

try: import configuration
except ImportError:
    print """\
Failed to import 'configuration' module.

Make sure the --etc-dir[=%s] and --identity[=%s] options
correctly define where the installed system's configuration is stored.""" % (arguments.etc_dir, arguments.identity)
    sys.exit(1)

install_data_path = os.path.join(configuration.paths.INSTALL_DIR, ".install.data")

if not os.path.isfile(install_data_path):
    print """\
%s: no such file

This installation of Critic appears to be incomplete or corrupt.""" % install_data_path
    sys.exit(1)

def deunicode(v):
    if type(v) == unicode: return v.encode("utf-8")
    elif type(v) == list: return map(deunicode, v)
    elif type(v) == dict: return dict([(deunicode(a), deunicode(b)) for a, b in v.items()])
    else: return v

try:
    with open(install_data_path, "r") as install_data:
        data = deunicode(json.load(install_data))
        if not isinstance(data, dict): raise ValueError
except ValueError:
    print """\
%s: failed to parse JSON object

This installation of Critic appears to be incomplete or corrupt.""" % install_data_path
    sys.exit(1)

print """
Critic Upgrade
==============
"""

git = data["installation.prereqs.git"]

if "sha1" not in data:
    try:
        guess_sha1 = installation.utils.run_git([git, "rev-parse", "HEAD@{1}"],
                                                cwd=installation.root_dir).strip()
    except:
        guess_sha1 = None

    print """
The SHA-1 of the commit you initially installed was not recorded.  This
means you installed a version before the install.py script was changed
to record the SHA-1 currently checked out."""

    if guess_sha1:
        print """
A reasonable guess is HEAD@{1}, or "where HEAD was before the last
operation that changed HEAD".  Otherwise, please figure out what you
installed.  If you need to guess, guessing on something too old (i.e.
a commit that is an ancestor of the actual commit) is safer than
guessing on something too recent."""
        default = "HEAD@{1}"
    else:
        print """
Please figure out what you installed.  If you need to guess, guessing
on something too old (i.e.  a commit that is an ancestor of the actual
commit) is safer than guessing on something too recent."""
        default = None

    print """
The commit can be specified as a SHA-1 or any symbolic ref understood
by "git rev-parse".
"""

    def revparse(value):
        return installation.utils.run_git([git, "rev-parse", "--verify", value],
                                          cwd=installation.root_dir).strip()

    def valid_commit(value):
        try:
            sha1 = revparse(value)
        except subprocess.CalledProcessError:
            return "not a valid ref (checked with \"git rev-parse --verify\")"

        try:
            installation.utils.run_git([git, "cat-file", "commit", sha1],
                                       cwd=installation.root_dir)
        except subprocess.CalledProcessError:
            return "not a commit"

    sha1 = revparse(installation.input.string(prompt="What commit was originally installed?",
                                              default=default,
                                              check=valid_commit))

    data["sha1"] = sha1

old_critic_sha1 = data["sha1"]
new_critic_sha1 = installation.utils.run_git([git, "rev-parse", "HEAD"],
                                             cwd=installation.root_dir).strip()
print """
Previously installed version: %s
Will now upgrade to version:  %s
""" % (old_critic_sha1, new_critic_sha1)

if old_critic_sha1 == new_critic_sha1:
    print "Old and new commit are the same, nothing to do."
    sys.exit(0)

if installation.utils.run_git([git, "status", "--porcelain"],
                              cwd=installation.root_dir).strip():
    print """
ERROR: This Git repository has local modifications.

Installing from a Git repository with local changes is not supported.
Please commit or stash the changes and then try again.
"""
    sys.exit(1)

try:
    try:
        if not installation.prereqs.check("upgrade", arguments):
            abort()
    except KeyboardInterrupt:
        abort()
    except SystemExit:
        raise
    except:
        print >>sys.stderr, "FAILED: installation.prereqs.check()"
        traceback.print_exc()
        abort()

    for module in installation.modules:
        try:
            if hasattr(module, "prepare") and not module.prepare("upgrade", arguments, data):
                abort()
        except KeyboardInterrupt:
            abort()
        except SystemExit:
            raise
        except:
            print >>sys.stderr, "FAILED: %s.upgrade()" % module.__name__
            traceback.print_exc()
            abort()

    if not arguments.dry_run:
        if not installation.apache.stop():
            abort()
        if not installation.initd.stop():
            abort()

    for module in installation.modules:
        try:
            if hasattr(module, "upgrade") and not module.upgrade(arguments, data):
                abort()
        except KeyboardInterrupt:
            abort()
        except SystemExit:
            raise
        except:
            print >>sys.stderr, "FAILED: %s.upgrade()" % module.__name__
            traceback.print_exc()
            abort()

    if not arguments.dry_run:
        # Before bugfix "Fix recreation of /var/run/critic/IDENTITY after reboot"
        # it was possible that /var/run/critic/IDENTITY was accidentally
        # recreated owned by root:root instead of critic:critic (on reboot).
        # If this had happened the service manager restart that is done during
        # upgrade would fail so upgrades always failed. Further, it was not
        # possible to write a migration script for this because migrations
        # execute after the service manager restart. Because of this the
        # following 3 line workaround was necessary:
        import configuration
        if os.path.exists(configuration.paths.RUN_DIR):
            os.chown(configuration.paths.RUN_DIR, installation.system.uid, installation.system.gid)

        if not installation.initd.start():
            abort()
        if not installation.apache.start():
            abort()

    data["sha1"] = new_critic_sha1

    with installation.utils.as_critic_system_user():
        import dbaccess
        db = dbaccess.connect()
        cursor = db.cursor()
        cursor.execute("UPDATE systemidentities SET installed_sha1=%s, installed_at=NOW() WHERE name=%s", (new_critic_sha1, arguments.identity))
        if not arguments.dry_run:
            db.commit()

    if not arguments.dry_run:
        with open(install_data_path, "w") as install_data:
            json.dump(data, install_data)

    for module in installation.modules:
        try:
            if hasattr(module, "finish"):
                module.finish()
        except:
            print >>sys.stderr, "WARNING: %s.finish() failed" % module.__name__
            traceback.print_exc()

    installation.utils.clean_root_pyc_files()

    print
    print "SUCCESS: Upgrade complete!"
    print
except SystemExit:
    raise
except:
    traceback.print_exc()
    abort()
