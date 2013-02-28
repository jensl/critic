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
import os.path

import argparse
import installation

parser = argparse.ArgumentParser(description="Critic upgrade script")

parser.add_argument("--etc-dir", default="/etc/critic", help="directory where the Critic system configuration is stored", action="store")
parser.add_argument("--identity", "-i", default="main", help="system identity to upgrade", action="store")
parser.add_argument("--dry-run", "-n", help="produce output but don't modify the system at all", action="store_true")

for module in installation.modules:
    if hasattr(module, "add_arguments"):
        module.add_arguments("upgrade", parser)

arguments = parser.parse_args()

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
correctly define where the installed system's configuration is stored.""" % (etc_path, arguments.etc_dir, arguments.identity)
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

if "sha1" not in data:
    try: guess_sha1 = installation.process.check_output([data["installation.prereqs.git"], "rev-parse", "HEAD@{1}"],
                                                        cwd=os.path.dirname(os.path.abspath(__file__)))
    except: guess_sha1 = None

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
        return installation.process.check_output([data["installation.prereqs.git"], "rev-parse", "--verify", value],
                                                 cwd=os.path.dirname(os.path.abspath(__file__))).strip()

    def valid_commit(value):
        try: sha1 = revparse(value)
        except: return "not a valid ref (checked with \"git rev-parse --verify\")"

        try: installation.process.check_output([data["installation.prereqs.git"], "cat-file", "commit", sha1],
                                               cwd=os.path.dirname(os.path.abspath(__file__)))
        except: return "not a commit"

    sha1 = revparse(installation.input.string(prompt="What commit was originally installed?",
                                              default=default,
                                              check=valid_commit))

    data["sha1"] = sha1

git = data["installation.prereqs.git"]

if installation.process.check_output([git, "status", "--porcelain"]).strip():
    print """
ERROR: This Git repository has local modifications.

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
        with open(install_data_path, "w") as install_data:
            json.dump(data, install_data)

    for module in installation.modules:
        try:
            if hasattr(module, "finish"):
                module.finish()
        except:
            print >>sys.stderr, "WARNING: %s.finish() failed" % module.__name__
            traceback.print_exc()

    print
    print "SUCCESS: Upgrade complete!"
    print
except SystemExit:
    raise
except:
    traceback.print_exc()
    abort()
