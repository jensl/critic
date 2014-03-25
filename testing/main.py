# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2013 Jens Lindström, Opera Software ASA
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

import sys
import os
import argparse
import logging
import re
import subprocess
import traceback
import time
import datetime

import testing

class Counters:
    def __init__(self):
        self.tests_run = 0
        self.tests_failed = 0
        self.errors_logged = 0
        self.warnings_logged = 0

counters = Counters()
logger = None

def run():
    global logger

    parser = argparse.ArgumentParser(description="Critic testing framework")

    parser.add_argument("--debug", action="store_true",
                        help="Enable DEBUG level logging")
    parser.add_argument("--debug-mails", action="store_true",
                        help="Log every mail sent by the tested system")
    parser.add_argument("--quiet", action="store_true",
                        help="Disable INFO level logging")

    parser.add_argument("--coverage", action="store_true",
                        help="Enable coverage measurement mode")
    parser.add_argument("--commit",
                        help="Commit (symbolic ref or SHA-1) to test [default=HEAD]")
    parser.add_argument("--upgrade-from",
                        help="Commit (symbolic ref or SHA-1) to install first and upgrade from")
    parser.add_argument("--strict-fs-permissions", action="store_true",
                        help="Set strict file-system permissions in guest OS")
    parser.add_argument("--test-extensions", action="store_true",
                        help="Test extensions")

    parser.add_argument("--local", action="store_true",
                        help="Run local standalone tests only")

    parser.add_argument("--vbox-host", default="host",
                        help="Host that's running VirtualBox [default=host]")
    parser.add_argument("--vm-identifier",
                        help="VirtualBox instance name or UUID")
    parser.add_argument("--vm-hostname",
                        help="VirtualBox instance hostname [default=VM_IDENTIFIER")
    parser.add_argument("--vm-snapshot", default="clean",
                        help="VirtualBox snapshot (name or UUID) to restore [default=clean]")
    parser.add_argument("--vm-ssh-port", type=int, default=22,
                        help="VirtualBox instance SSH port [default=22]")
    parser.add_argument("--vm-http-port", type=int, default=80,
                        help="VirtualBox instance HTTP port [default=80]")

    parser.add_argument("--git-daemon-port", type=int,
                        help="Port to tell 'git daemon' to bind to")
    parser.add_argument("--cache-dir", default="testing/cache",
                        help="Directory where cache files are stored")

    parser.add_argument("--pause-before", action="append",
                        help="Pause testing before specified test(s)")
    parser.add_argument("--pause-after", action="append",
                        help="Pause testing before specified test(s)")
    parser.add_argument("--pause-on-failure", action="store_true",
                        help="Pause testing after each failed test")
    parser.add_argument("--pause-upgrade-loop", action="store_true",
                        help="Support upgrading the tested system while paused")
    parser.add_argument("--pause-upgrade-hook", action="append",
                        help="Command to run (locally) before upgrading")

    parser.add_argument("test", nargs="*",
                        help="Specific tests to run [default=all]")

    arguments = parser.parse_args()

    class CountingLogger(object):
        def __init__(self, real, counters):
            self.real = real
            self.counters = counters

        def log(self, level, message):
            if level == logging.ERROR:
                self.counters.errors_logged += 1
            elif level == logging.WARNING:
                self.counters.warnings_logged += 1
            for line in message.splitlines() or [""]:
                self.real.log(level, line)
        def debug(self, message):
            self.log(logging.DEBUG, message)
        def info(self, message):
            self.log(logging.INFO, message)
        def warning(self, message):
            self.log(logging.WARNING, message)
        def error(self, message):
            self.log(logging.ERROR, message)
        def exception(self, message):
            self.log(logging.ERROR, message + "\n" + traceback.format_exc())

    logger = testing.configureLogging(
        arguments, wrap=lambda logger: CountingLogger(logger, counters))
    logger.info("""\
Critic Testing Framework
========================

""")

    if not arguments.local and not arguments.vm_identifier:
        logger.error("Must specify one of --local and --vm-identifier!")
        return

    if arguments.local:
        incompatible_arguments = []

        # This is not a complete list; just those that are most significantly
        # incompatible or irrelevant with --local.
        if arguments.commit:
            incompatible_arguments.append("--commit")
        if arguments.upgrade_from:
            incompatible_arguments.append("--upgrade-from")
        if arguments.coverage:
            incompatible_arguments.append("--coverage")
        if arguments.test_extensions:
            incompatible_arguments.append("--strict-fs-permissions")
        if arguments.test_extensions:
            incompatible_arguments.append("--test-extensions")
        if arguments.vm_identifier:
            incompatible_arguments.append("--vm-identifier")

        if incompatible_arguments:
            logger.error("These arguments can't be combined with --local:\n  " +
                         "\n  ".join(incompatible_arguments))
            return

    import_errors = False

    try:
        import requests
    except ImportError:
        logger.error("Failed to import 'requests'!")
        import_errors = True

    try:
        import BeautifulSoup
    except ImportError:
        logger.error("Failed to import 'BeautifulSoup'!")
        import_errors = True

    git_version = subprocess.check_output(["git", "--version"]).strip()
    m = re.search("(\d+)\.(\d+)\.(\d+)(?:[^\d]+|$)", git_version)
    if not m:
        logger.warning("Failed to parse host-side git version number: '%s'" % git_version)
    else:
        version_tuple = tuple(map(int, m.groups()))
        if version_tuple >= (1, 8, 5):
            logger.debug("Using Git version %s on host." % git_version)
        else:
            logger.error("Git version on host machine must be version 1.8.5 or above (detected version %s)." % git_version)
            logger.error("Earlier Git versions crashed with SIGBUS causing test suite flakiness.")
            import_errors = True

    if import_errors:
        logger.error("Required software missing; see testing/USAGE.md for details.")
        return

    if arguments.test_extensions:
        # Check that the v8-jsshell submodule is checked out if extension
        # testing was requested.
        output = subprocess.check_output(["git", "submodule", "status",
                                          "installation/externals/v8-jsshell"])
        if output.startswith("-"):
            logger.error("""\
The v8-jsshell submodule must be checked for extension testing.  Please run
  git submodule update --init installation/externals/v8-jsshell
first or run this script without --test-extensions.""")
            return

    if not arguments.local:
        # Note: we are not ignoring typical temporary editor files such as the
        # ".#<name>" files created by Emacs when a buffer has unsaved changes.
        # This is because unsaved changes in an editor is probably also
        # something you don't want to test with.

        locally_modified_paths = []

        status_output = subprocess.check_output(
            ["git", "status", "--porcelain"])

        for line in status_output.splitlines():
            locally_modified_paths.extend(line[3:].split(" -> "))

        tests_modified = []
        input_modified = []
        other_modified = []

        for path in locally_modified_paths:
            if path.startswith("testing/input/"):
                input_modified.append(path)
            elif path.startswith("testing/"):
                tests_modified.append(path)
            else:
                other_modified.append(path)

        if input_modified:
            logger.error("Test input files locally modified:\n  " +
                         "\n  ".join(input_modified))
        if other_modified:
            logger.error("Critic files locally modified:\n  " +
                         "\n  ".join(other_modified))
        if input_modified or other_modified:
            logger.error("Please commit or stash local modifications before "
                         "running tests.")
            return

        if tests_modified:
            logger.warning("Running tests using locally modified files:\n  " +
                           "\n  ".join(tests_modified))

    tested_commit = subprocess.check_output(
        ["git", "rev-parse", "--verify", arguments.commit or "HEAD"]).strip()

    if arguments.upgrade_from:
        install_commit = subprocess.check_output(
            ["git", "rev-parse", "--verify", arguments.upgrade_from]).strip()
        upgrade_commit = tested_commit
    else:
        install_commit = tested_commit
        upgrade_commit = None

    install_commit_description = subprocess.check_output(
        ["git", "log", "--oneline", "-1", install_commit]).strip()

    if upgrade_commit:
        upgrade_commit_description = subprocess.check_output(
            ["git", "log", "--oneline", "-1", upgrade_commit]).strip()
    else:
        upgrade_commit_description = None

    flags_on = set()
    flags_off = set()

    try:
        if arguments.local:
            frontend = None
            instance = testing.local.Instance()
            flags_on.add("local")
        else:
            frontend = testing.frontend.Frontend(
                hostname=arguments.vm_hostname or arguments.vm_identifier,
                http_port=arguments.vm_http_port)

            instance = testing.virtualbox.Instance(
                arguments,
                install_commit=(install_commit, install_commit_description),
                upgrade_commit=(upgrade_commit, upgrade_commit_description),
                frontend=frontend)
    except testing.Error as error:
        logger.error(error.message)
        return

    tests, dependencies = testing.findtests.selectTests(
        arguments.test, strict=False, flags_on=flags_on, flags_off=flags_off)

    if not tests:
        logger.error("No tests selected!")
        return

    def pause():
        if arguments.pause_upgrade_loop:
            print "Testing paused."

            while True:
                testing.pause("Press ENTER to upgrade (to HEAD), CTRL-c to stop: ")

                for command in arguments.pause_upgrade_hook:
                    subprocess.check_call(command, shell=True)

                repository.push("HEAD")

                instance.execute(["git", "fetch", "origin", "master"], cwd="critic")
                instance.upgrade_commit = "FETCH_HEAD"
                instance.upgrade()
        else:
            testing.pause("Testing paused.  Press ENTER to continue: ")

    pause_before = pause_after = set()

    if arguments.pause_before:
        pause_before = testing.findtests.filterPatterns(arguments.pause_before)
        pause_before_tests, _ = testing.findtests.selectTests(pause_before,
                                                              strict=True)
        pause_before_tests = set(pause_before_tests)
        pause_before_groups = set(pause_before)

        def maybe_pause_before(test):
            def do_pause(what):
                logger.info("Pausing before: %s" % what)
                pause()

            if test in pause_before_tests:
                do_pause(test)
            else:
                for group in test.groups:
                    if group in pause_before_groups \
                            and test == all_groups[group][0]:
                        do_pause(group)
                        break
    else:
        def maybe_pause_before(test):
            pass

    if arguments.pause_after:
        pause_after = testing.findtests.filterPatterns(arguments.pause_after)
        pause_after_tests, _ = testing.findtests.selectTests(pause_after,
                                                             strict=True)
        pause_after_tests = set(pause_after_tests)
        pause_after_groups = set(pause_after)

        def maybe_pause_after(test):
            def do_pause(what):
                logger.info("Pausing after: %s" % what)
                pause()

            if test in pause_after_tests:
                do_pause(test)
            else:
                for group in test.groups:
                    if group in pause_after_groups \
                            and test == all_groups[group][-1]:
                        do_pause(group)
                        break
    else:
        def maybe_pause_after(test):
            pass

    root_groups = {}
    all_groups = {}

    for test in tests:
        for group in test.groups:
            all_groups.setdefault(group, []).append(test)
        root_groups.setdefault(test.groups[0], []).append(test)

    failed_tests = set()

    def run_group(group_name, tests):
        scope = { "testing": testing,
                  "logger": logger,
                  "instance": instance }

        if not arguments.local:
            scope.update({ "frontend": frontend,
                           "repository": repository,
                           "mailbox": mailbox })

        try:
            for test in tests:
                if test.dependencies & failed_tests:
                    logger.info("Skipping %s (failed dependency)" % test)
                    continue

                maybe_pause_before(test)

                if test in dependencies:
                    logger.info("Running: %s (dependency)" % test)
                else:
                    logger.info("Running: %s" % test)

                counters.tests_run += 1

                try:
                    errors_before = counters.errors_logged
                    execfile(os.path.join("testing/tests", test.filename),
                             scope.copy())
                    if errors_before < counters.errors_logged:
                        raise testing.TestFailure
                except testing.TestFailure as failure:
                    counters.tests_failed += 1

                    failed_tests.add(test)

                    if failure.message:
                        logger.error(failure.message)

                    if mailbox:
                        while True:
                            try:
                                mail = mailbox.pop(
                                    accept=testing.mailbox.ToRecipient(
                                        "system@example.org"),
                                    timeout=1)
                            except testing.mailbox.MissingMail:
                                break
                            else:
                                logger.error("System message: %s\n  %s"
                                             % (mail.header("Subject"),
                                                "\n  ".join(mail.lines)))

                    if arguments.pause_on_failure:
                        pause()
                except testing.NotSupported as not_supported:
                    failed_tests.add(test)
                    logger.info("Test not supported: %s" % not_supported.message)
                else:
                    maybe_pause_after(test)
        except KeyboardInterrupt:
            logger.error("Testing aborted.")
            return False
        except testing.Error as error:
            if error.message:
                logger.exception(error.message)
            if arguments.pause_on_failure:
                pause()
            return False
        except Exception:
            logger.exception("Unexpected exception!")
            if arguments.pause_on_failure:
                pause()
            return False
        else:
            return True

    for group_name in sorted(root_groups.keys()):
        if arguments.local:
            repository = None
            mailbox = None

            run_group(group_name, all_groups[group_name])
        else:
            repository = testing.repository.Repository(
                arguments.vbox_host,
                arguments.git_daemon_port,
                tested_commit,
                arguments.vm_hostname)
            mailbox = testing.mailbox.Mailbox({ "username": "smtp_username",
                                                "password": "SmTp_PaSsWoRd" },
                                              arguments.debug_mails)

            with repository:
                with mailbox:
                    if not repository.export():
                        return

                    with instance:
                        instance.mailbox = mailbox

                        testing.utils.instance = instance
                        testing.utils.frontend = frontend

                        if run_group(group_name, all_groups[group_name]):
                            instance.finish()

                    mailbox.check_empty()

def main():
    start_time = time.time()

    run()

    time_taken = str(datetime.timedelta(seconds=round(time.time() - start_time)))

    logger.info("""
Test summary
============
Tests run:       %9d
Tests failed:    %9d
Errors logged:   %9d
Warnings logged: %9d
Time taken:      %9s
""" % (counters.tests_run,
       counters.tests_failed,
       counters.errors_logged,
       counters.warnings_logged,
       time_taken))

    if counters.tests_failed or counters.errors_logged:
        sys.exit(1)

if __name__ == "__main__":
    main()
