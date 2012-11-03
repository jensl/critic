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

import os.path
import installation

etc_dir = "/etc/critic"
install_dir = "/usr/share/critic"
data_dir = "/var/lib/critic"
cache_dir = "/var/cache/critic"
git_dir = "/var/git"
log_dir = "/var/log/critic"
run_dir = "/var/run/critic"

def prepare(arguments):
    global etc_dir, install_dir, data_dir, cache_dir, git_dir, log_dir, run_dir

    all_ok = True

    print """
Critic Installation: Paths
==========================
"""

    def is_good_dir(path):
        if not path: return "empty path"
        elif not path.startswith("/"): return "must be an absolute path"
        elif os.path.exists(path) and not os.path.isdir(path):
            return "exists and is not a directory"

    def is_new_dir(path):
        error = is_good_dir(path)
        if error: return error
        if os.path.exists(path): return "already exists"

    if arguments.etc_dir:
        error = is_new_dir(arguments.etc_dir)
        if error:
            print "Invalid --etc-dir argument: %s." % error
            return False
        etc_dir = arguments.etc_dir
    else:
        all_ok = False
        etc_dir = installation.input.string(prompt="Where should Critic's configuration files be installed?",
                                            default=etc_dir,
                                            check=is_new_dir)

    if arguments.install_dir:
        error = is_new_dir(arguments.install_dir)
        if error:
            print "Invalid --install-dir argument: %s." % error
            return False
        install_dir = arguments.install_dir
    else:
        all_ok = False
        install_dir = installation.input.string(prompt="Where should Critic's source code be installed?",
                                                default=install_dir,
                                                check=is_new_dir)

    if arguments.data_dir:
        error = is_new_dir(arguments.data_dir)
        if error:
            print "Invalid --data-dir argument: %s." % error
            return False
        data_dir = arguments.data_dir
    else:
        all_ok = False
        data_dir = installation.input.string(prompt="Where should Critic's persistent data files live?",
                                             default=data_dir,
                                             check=is_new_dir)

    if arguments.cache_dir:
        error = is_new_dir(arguments.cache_dir)
        if error:
            print "Invalid --cache-dir argument: %s." % error
            return False
        cache_dir = arguments.cache_dir
    else:
        all_ok = False
        cache_dir = installation.input.string(prompt="Where should Critic's temporary data files live?",
                                              default=cache_dir,
                                              check=is_new_dir)

    if arguments.git_dir:
        error = is_new_dir(arguments.git_dir)
        if error:
            print "Invalid --git-dir argument: %s." % error
            return False
        git_dir = arguments.git_dir
    else:
        all_ok = False
        git_dir = installation.input.string(prompt="Where should Critic's Git repositories live?",
                                            default=git_dir,
                                            check=is_new_dir)

    if arguments.log_dir:
        error = is_new_dir(arguments.log_dir)
        if error:
            print "Invalid --log-dir argument: %s." % error
            return False
        log_dir = arguments.log_dir
    else:
        all_ok = False
        log_dir = installation.input.string(prompt="Where should Critic's log files live?",
                                            default=log_dir,
                                            check=is_good_dir)

    if arguments.run_dir:
        error = is_new_dir(arguments.run_dir)
        if error:
            print "Invalid --run-dir argument: %s." % error
            return False
        run_dir = arguments.run_dir
    else:
        all_ok = False
        run_dir = installation.input.string(prompt="Where should Critic's runtime files live?",
                                            default=run_dir,
                                            check=is_good_dir)

    if all_ok: print "All okay."

    return True

created = []

def execute():
    import errno
    import stat

    def mkdir(path, mode=0750):
        global created
        if not os.path.isdir(path):
            if not os.path.isdir(os.path.dirname(path)):
                mkdir(os.path.dirname(path), mode)

            print "Creating directory '%s' ..." % path
            os.mkdir(path, mode)
            created.append(path)
            os.chown(path, installation.system.uid, installation.system.gid)

    mkdir(os.path.join(etc_dir, "main"))
    mkdir(install_dir, 0755)
    mkdir(os.path.join(data_dir, "relay"))
    mkdir(os.path.join(data_dir, "outbox", "sent"), mode=0700)
    mkdir(os.path.join(cache_dir, "highlight"))
    mkdir(git_dir)
    mkdir(os.path.join(log_dir, "main"))
    mkdir(os.path.join(run_dir, "main", "sockets"))
    mkdir(os.path.join(run_dir, "main", "wsgi"))

    os.chmod(git_dir, 0770 | stat.S_ISUID | stat.S_ISGID)

    return True

def undo():
    map(os.rmdir, reversed(created))
