# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2012 Martin Olsson
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
import grp
import sys
import argparse
import subprocess

import installation

def enum(*sequential, **named):
    enums = dict(zip(sequential, range(len(sequential))), **named)
    return type('Enum', (), enums)

ExitStatus = enum('EXIT_SUCCESS', 'MUST_RUN_AS_ROOT', 'INVALID_ETC_DIR', 'UNEXPECTED_ERROR')

def check(value):
    if value.strip() != "deletemydata":
        return "to continue with uninstall, enter 'deletemydata', to abort uninstall press CTRL-C"

def abort_if_no_keep_going_param(arguments, error_msg):
    if not arguments.keep_going:
        print error_msg
        print "Unexpected error encountered.  Critic uninstall aborted."
        print "Re-run with --keep-going to ignore errors."
        sys.exit(ExitStatus.UNEXPECTED_ERROR)

def get_all_configurations(arguments):
    configurations = []
    etc_dir = arguments.etc_dir
    original_sys_path = list(sys.path)

    for critic_instance in os.listdir(etc_dir):
        etc_path = os.path.join(etc_dir, critic_instance)

        if not os.path.isdir(etc_path):
            abort_if_no_keep_going_param(arguments, "ERROR: %s is not a directory." % etc_path)

        sys.path = list(original_sys_path)
        sys.path.insert(0, etc_path)

        try:
            import configuration
            configurations.append(configuration)
        except ImportError:
            abort_if_no_keep_going_param(arguments, "ERROR: Failed to load Critic instance configuration from %s." % etc_path)

    sys.path = list(original_sys_path)
    return configurations

def run_command(arguments, command_parts):
    try:
        subprocess.check_output(command_parts)
    except:
        abort_if_no_keep_going_param(arguments, "Error while running command: " + ' '.join(command_parts))

def rmdir_if_empty(directories):
    for dir in directories:
        try:
            os.rmdir(dir)
        except OSError:
            pass

def main():
    parser = argparse.ArgumentParser(description="Critic uninstall script")
    parser.add_argument("--headless", help=argparse.SUPPRESS, action="store_true")
    parser.add_argument("--etc-dir", default="/etc/critic", help="root directory for Critic system configurations i.e. specifying /etc/critic will read configuration data from /etc/critic/*/configuration/*.py", action="store")
    parser.add_argument("--keep-going", help="keep going even if errors are encountered (useful for purging broken installations)", action="store_true")
    arguments = parser.parse_args()

    if os.getuid() != 0:
        print """
ERROR: This script must be run as root.
"""
        sys.exit(ExitStatus.MUST_RUN_AS_ROOT)

    if not arguments.headless:
        print """\
!!!! WARNING !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
This uninstall script will delete Critic, all Critic logs, caches and
configuration files, and it will also DELETE ALL DATA related to Critic.
It will drop the entire Critic database from postgresql and it will
permanently delete the Critic git repositories.  If there are multiple
instances of Critic on this system, all of them will be removed.
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

This step cannot be undone! To abort the uninstall script, press CTRL-C now.
"""
        installation.input.string("To continue the uninstall script and DELETE ALL YOUR DATA, enter 'deletemydata' here:", default="", check=check)

    if not os.path.isdir(arguments.etc_dir):
        print "%s: no such directory.  Invalid --etc-dir parameter." % arguments.etc_dir
        sys.exit(ExitStatus.INVALID_ETC_DIR)

    run_command(arguments, ["service", "apache2", "stop"])

    # Sets of system users/groups to delete will be collected (to avoid trying to delete the same user/group twice).
    users_to_delete = set()
    groups_to_delete = set()

    for configuration in get_all_configurations(arguments):
        users_to_delete.add(configuration.base.SYSTEM_USER_NAME)
        groups_to_delete.add(configuration.base.SYSTEM_GROUP_NAME)

        run_command(arguments, ["service", "critic-%s" % configuration.base.SYSTEM_IDENTITY, "stop"])
        run_command(arguments, ["rm", "-rf", configuration.paths.DATA_DIR, configuration.paths.LOG_DIR])
        run_command(arguments, ["rm", "-rf", configuration.paths.CACHE_DIR, configuration.paths.RUN_DIR])
        run_command(arguments, ["rm", "-rf", configuration.paths.INSTALL_DIR, configuration.paths.GIT_DIR])
        run_command(arguments, ["rm", "-f", "/etc/apache2/sites-available/critic-%s" % configuration.base.SYSTEM_IDENTITY])
        run_command(arguments, ["rm", "-f", "/etc/apache2/sites-enabled/critic-%s" % configuration.base.SYSTEM_IDENTITY])
        run_command(arguments, ["rm", "-f", "/etc/init.d/critic-%s" % configuration.base.SYSTEM_IDENTITY])
        run_command(arguments, ["update-rc.d", "critic-%s" % configuration.base.SYSTEM_IDENTITY, "remove"])

        # Typically the postgres user does not have access to the cwd during uninstall so we use "-i"
        # with sudo which makes the command run with the postgres user's homedir as cwd instead.
        # This avoids a harmless but pointless error message "could not change directory to X" when the
        # /usr/bin/psql perl script tries to chdir back to the previous cwd after doing some stuff.
        run_command(arguments, ["sudo", "-u", "postgres", "-i", "psql", "-v", "ON_ERROR_STOP=1", "-c", "DROP DATABASE IF EXISTS %s;" % configuration.database.PARAMETERS["database"]])
        run_command(arguments, ["sudo", "-u", "postgres", "-i", "psql", "-v", "ON_ERROR_STOP=1", "-c", "DROP ROLE IF EXISTS %s;" % configuration.database.PARAMETERS["user"]])

    for user in users_to_delete:
        run_command(arguments, ["deluser", "--system", user])

    for group in groups_to_delete:
        try:
            # Revoke push rights for all users that have been added to the Critic system group.
            # delgroup doesn't do this automatically and we want to avoid users gettings errors like:
            # "groups: cannot find name for group ID 132"
            for group_member in grp.getgrnam(group).gr_mem:
                subprocess.check_output(["gpasswd", "-d", group_member, group])
        except KeyError:
            abort_if_no_keep_going_param(arguments, "ERROR: Could not find group '%s'." % group)
        run_command(arguments, ["delgroup", "--system", group])

    # Delete non-instance specific parts.
    run_command(arguments, ["rm", "-rf", arguments.etc_dir, "/usr/bin/criticctl"])
    run_command(arguments, ["service", "apache2", "restart"])

    # When default paths are used in install.py we put some extra effort into
    # completely cleaning the system on uninstall, with custom paths it's
    # trickier to know if the user really wants to delete empty parent dirs.
    rmdir_if_empty(["/var/log/critic", "/var/run/critic", "/var/cache/critic"])

    run_command(arguments, ["rm", "-f", os.path.join(installation.root_dir, ".install.data")])

    print
    print "SUCCESS: Uninstall complete."
    print

    return ExitStatus.EXIT_SUCCESS

if __name__ == "__main__":
    sys.exit(main())
