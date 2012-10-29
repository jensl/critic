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

if os.getuid() != 0:
    print """
ERROR: This script must be run as root.
"""
    sys.exit(1)

if sys.version_info[0] != 2 or sys.version_info[1] < 7:
    print """\
Unsupported Python version!  Critic requires Python 2.7.x or later,
but not Python 3.x.  This script must be run in the Python interpreter
that will be used to run Critic."""
    sys.exit(2)

import argparse
import installation

parser = argparse.ArgumentParser(description="Critic installation script")

parser.add_argument("--etc-dir", help="directory where the Critic system configuration is stored", action="store")
parser.add_argument("--install-dir", help="directory where the Critic source code is installed", action="store")
parser.add_argument("--data-dir", help="directory where Critic's persistent data files are stored", action="store")
parser.add_argument("--cache-dir", help="directory where Critic's temporary data files are stored", action="store")
parser.add_argument("--git-dir", help="directory where the main Git repositories are stored", action="store")
parser.add_argument("--log-dir", help="directory where Critic's log files are stored", action="store")
parser.add_argument("--run-dir", help="directory where Critic's runtime files are stored", action="store")

parser.add_argument("--system-hostname", help="FQDN of the system", action="store")
parser.add_argument("--system-username", help="name of system user to run as", action="store")
parser.add_argument("--system-email", help="address used as sender of emails", action="store")
parser.add_argument("--system-groupname", help="name of system group to run as", action="store")

parser.add_argument("--auth-mode", help="user authentication mode", choices=["host", "critic"], action="store")

parser.add_argument("--admin-username", help="name of Critic administrator user", action="store")
parser.add_argument("--admin-email", help="email address to Critic administrator user", action="store")
parser.add_argument("--admin-fullname", help="Critic administrator user's full name", action="store")

arguments = parser.parse_args()

def abort():
    print
    print "ERROR: Installation aborted."
    print

    for module in reversed(installation.modules):
        try: module.undo()
        except:
            print >>sys.stderr, "FAILED: %s.undo()" % module.__name__
            traceback.print_exc()

    sys.exit(1)

try:
    for module in installation.modules:
        try:
            if not module.prepare(arguments):
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

    data = {}

    for module in installation.modules:
        for name in dir(module):
            if name.startswith("__"): continue
            value = getattr(module, name)
            if isinstance(value, str):
                data["%s.%s" % (module.__name__, name)] = value

    with open(".install.data", "w") as install_data:
        json.dump(data, install_data)

    for module in installation.modules:
        try:
            if not module.execute():
                abort()
        except KeyboardInterrupt:
            abort()
        except SystemExit:
            raise
        except:
            print >>sys.stderr, "FAILED: %s.execute()" % module.__name__
            traceback.print_exc()
            abort()

    print
    print "SUCCESS: Installation complete!"
    print
except SystemExit:
    raise
except:
    traceback.print_exc()
    abort()
