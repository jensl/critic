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
import subprocess

# To avoid accidentally creating files owned by root.
sys.dont_write_bytecode = True

# Python version check is done before imports below so
# that python 2.6/2.5 users can see the error message.
import pythonversion
pythonversion.check()

if sys.flags.optimize > 0:
    print """
ERROR: Please run this script without -O or -OO options.
"""
    sys.exit(1)

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
parser.add_argument("--force", "-f", help="force upgrade even if same commit is checked out", action="store_true")

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

    sys.exit(1)

data = installation.utils.read_install_data(arguments)

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

old_lifecycle = installation.utils.read_lifecycle(git, old_critic_sha1)
new_lifecycle = installation.utils.read_lifecycle()

if old_lifecycle["stable"] != new_lifecycle["stable"]:
    if old_lifecycle["stable"]:
        print """
WARNING: You're about to switch to an unstable development version of Critic!

If this is a production system, you are most likely better off staying on the
current branch, or switching to the latest stable branch, if there the current
branch isn't it.

The latest stable branch is the default branch (i.e. HEAD) in Critic's GitHub
repository at

  https://github.com/jensl/critic.git

To interrogate it from the command-line, run

  $ git ls-remote --symref https://github.com/jensl/critic.git HEAD

HINT: If you installed from the 'master' branch prior to October 2017, then it
      was at that time a stable branch (and also the only available option.)
      At this point in time, a stable branch 'stable/1' was branched off, and
      'master' became an unstable development branch.

      In other words, if you are currently on 'master', you most likely want to
      switch to 'stable/1', or the latest stable branch (see above,) now.
"""

        if not installation.input.yes_or_no(
                "Do you want to continue upgrading to the unstable version?",
                default=arguments.headless):
            print
            print "Installation aborted."
            print
            sys.exit(1)
    else:
        print """
NOTE: Switching from an unstable version to a stable version.
"""

print """
Previously installed version: %s
Will now upgrade to version:  %s
""" % (old_critic_sha1, new_critic_sha1)

if old_critic_sha1 == new_critic_sha1 and not arguments.force:
    print "Old and new commit are the same, nothing to do."
    sys.exit(0)

status_output = installation.utils.run_git([git, "status", "--porcelain"],
                                           cwd=installation.root_dir).strip()

if status_output:
    print """\
ERROR: This Git repository has local modifications."""

    if len(status_output.splitlines()) \
            and "installation/externals/v8-jsshell" in status_output:
        print """\
HINT: You might just need to run "git submodule update --recursive"."""

    print """
Installing from a Git repository with local changes is not supported.
Please commit or stash the changes and then try again.
"""
    sys.exit(1)

try:
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
        if not installation.httpd.stop():
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

    import configuration

    if not arguments.dry_run:
        # Before bugfix "Fix recreation of /var/run/critic/IDENTITY after reboot"
        # it was possible that /var/run/critic/IDENTITY was accidentally
        # recreated owned by root:root instead of critic:critic (on reboot).
        # If this had happened the service manager restart that is done during
        # upgrade would fail so upgrades always failed. Further, it was not
        # possible to write a migration script for this because migrations
        # execute after the service manager restart. Because of this the
        # following 3 line workaround was necessary:

        if os.path.exists(configuration.paths.RUN_DIR):
            os.chown(configuration.paths.RUN_DIR, installation.system.uid, installation.system.gid)

        if not installation.initd.start():
            abort()
        if not installation.httpd.start():
            abort()

    data["sha1"] = new_critic_sha1

    with installation.utils.as_critic_system_user():
        import dbaccess
        db = dbaccess.connect()
        cursor = db.cursor()
        cursor.execute("UPDATE systemidentities SET installed_sha1=%s, installed_at=NOW() WHERE name=%s", (new_critic_sha1, arguments.identity))
        if not arguments.dry_run:
            db.commit()

    for module in installation.modules:
        try:
            if hasattr(module, "finish"):
                module.finish("upgrade", arguments, data)
        except:
            print >>sys.stderr, "WARNING: %s.finish() failed" % module.__name__
            traceback.print_exc()

    installation.utils.write_install_data(arguments, data)
    installation.utils.clean_root_pyc_files()

    print
    print "SUCCESS: Upgrade complete!"
    print

    if configuration.extensions.ENABLED:
        try:
            installation.utils.run_git(
                [git, "diff", "--quiet",
                 "%s..%s" % (old_critic_sha1, new_critic_sha1),
                 "--", "installation/externals/v8-jsshell"])
        except subprocess.CalledProcessError:
            # Non-zero exit status means there were changes.
            print """
Updated v8-jsshell submodule
============================

The v8-jsshell program used to run extensions has been updated and needs to be
rebuilt.  If this is not done, the extensions mechanism may malfunction.  It can
be done manually later by running this command as root:

  python extend.py
"""

            rebuild_v8_jsshell = installation.input.yes_or_no(
                "Do you want to rebuild the v8-jsshell program now?",
                default=True)

            if rebuild_v8_jsshell:
                try:
                    args = []
                    if arguments.headless:
                        args.append("--headless")
                    subprocess.check_call([sys.executable, "extend.py"] + args)
                except subprocess.CalledProcessError:
                    # We have already finished the main upgrade, so just
                    # propagate the exit status if extend.py failed.  It will
                    # have output enough error messages, for sure.
                    sys.exit(1)

except SystemExit:
    raise
except:
    traceback.print_exc()
    abort()
