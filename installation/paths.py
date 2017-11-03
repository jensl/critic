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
import shutil

import installation

etc_dir = "/etc/critic"
bin_dir = "/usr/bin"
install_dir = "/usr/share/critic"
data_dir = "/var/lib/critic"
cache_dir = "/var/cache/critic"
git_dir = "/var/git"
log_dir = "/var/log/critic"
run_dir = "/var/run/critic"

def add_arguments(mode, parser):
    if mode == "install":
        parser.add_argument("--etc-dir", help="directory where the Critic system configuration is stored", action="store")
        parser.add_argument("--bin-dir", help="directory where the Critic system executables are installed", action="store")
        parser.add_argument("--install-dir", help="directory where the Critic source code is installed", action="store")
        parser.add_argument("--data-dir", help="directory where Critic's persistent data files are stored", action="store")
        parser.add_argument("--cache-dir", help="directory where Critic's temporary data files are stored", action="store")
        parser.add_argument("--git-dir", help="directory where the main Git repositories are stored", action="store")
        parser.add_argument("--log-dir", help="directory where Critic's log files are stored", action="store")
        parser.add_argument("--run-dir", help="directory where Critic's runtime files are stored", action="store")

def prepare(mode, arguments, data):
    global etc_dir, install_dir, data_dir, cache_dir, git_dir, log_dir, run_dir

    if mode == "install":
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
            if os.path.exists(path):
                return "directory already exists (NOTE: if Critic is already " \
                       "installed and you want to upgrade to the latest " \
                       "version of Critic, then run upgrade.py rather than " \
                       "re-running install.py)"

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
    else:
        import configuration

        def strip_identity(path):
            if os.path.basename(path) == configuration.base.SYSTEM_IDENTITY:
                return os.path.dirname(path)
            else:
                return path

        etc_dir = strip_identity(configuration.paths.CONFIG_DIR)
        install_dir = configuration.paths.INSTALL_DIR
        data_dir = configuration.paths.DATA_DIR
        cache_dir = strip_identity(configuration.paths.CACHE_DIR)
        git_dir = configuration.paths.GIT_DIR
        log_dir = strip_identity(configuration.paths.LOG_DIR)
        run_dir = strip_identity(configuration.paths.RUN_DIR)

    data["installation.paths.etc_dir"] = etc_dir
    data["installation.paths.install_dir"] = install_dir
    data["installation.paths.data_dir"] = data_dir
    data["installation.paths.cache_dir"] = cache_dir
    data["installation.paths.git_dir"] = git_dir
    data["installation.paths.log_dir"] = log_dir
    data["installation.paths.run_dir"] = run_dir

    return True

created = []

def mkdir(path, mode=0750):
    global created
    if not os.path.isdir(path):
        if not os.path.isdir(os.path.dirname(path)):
            mkdir(os.path.dirname(path), mode)

        if not installation.quiet:
            print "Creating directory '%s' ..." % path

        os.mkdir(path, mode)
        created.append(path)
        os.chown(path, installation.system.uid, installation.system.gid)

def mkdirs():
    import stat

    mkdir(os.path.join(etc_dir, "main"))
    mkdir(bin_dir)
    mkdir(install_dir, 0755)
    mkdir(os.path.join(data_dir, "relay"))
    mkdir(os.path.join(data_dir, "temporary"))
    mkdir(os.path.join(data_dir, "outbox", "sent"), mode=0700)
    mkdir(os.path.join(cache_dir, "main", "highlight"))
    mkdir(git_dir)
    mkdir(os.path.join(log_dir, "main"))
    mkdir(os.path.join(run_dir, "main", "sockets"), mode=0755)
    mkdir(os.path.join(run_dir, "main", "wsgi"))

    if installation.config.coverage_dir:
        mkdir(installation.config.coverage_dir)

    os.chmod(git_dir, 0770 | stat.S_ISUID | stat.S_ISGID)

def install(data):
    mkdirs()
    return True

def upgrade(arguments, data):
    mkdirs()
    return True

def undo():
    map(shutil.rmtree, reversed(created))
