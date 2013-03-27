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

import os
import time
import tempfile
import shutil
import logging
import subprocess

logger = logging.getLogger("critic")

class Repository(object):
    def __init__(self, tested_commit):
        self.base_path = tempfile.mkdtemp()
        self.path = os.path.join(self.base_path, "critic.git")
        self.name = "t%d" % (int(time.time() * 1000) % 1000000)

        logger.debug("Creating temporary repository: %s" % self.path)

        subprocess.check_output(
            ["git", "clone", "--bare", os.getcwd()],
            cwd=self.base_path)

        subprocess.check_output(
            ["git", "remote", "add", self.name, self.path])

        subprocess.check_output(
            ["git", "push", "--quiet", self.name,
             "%s:refs/heads/tested" % tested_commit])

    def export(self):
        self.daemon = subprocess.Popen(
            ["git", "daemon", "--reuseaddr", "--export-all",
             "--base-path=%s" % self.base_path, self.path])

        time.sleep(1)

        pid, status = os.waitpid(self.daemon.pid, os.WNOHANG)
        if pid != 0:
            self.daemon = None
            logger.error("Failed to export repository!")
            return False

        logger.info("Exported repository: %s" % self.path)
        return True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        try:
            if self.daemon:
                self.daemon.terminate()
                self.daemon.wait()
        except:
            logger.exception("Repository clean-up failed!")

        try:
            subprocess.check_output(
                ["git", "remote", "rm", self.name])
        except:
            logger.exception("Repository clean-up failed!")

        try:
            shutil.rmtree(self.base_path)
        except:
            logger.exception("Repository clean-up failed!")

        return False
