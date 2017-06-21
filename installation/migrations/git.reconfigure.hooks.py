# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2017 the Critic contributors, Opera Software ASA
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
import installation
import configuration

hook_script = os.path.join(configuration.paths.INSTALL_DIR,
                           "hooks", "pre-post-receive.py")

# Handles command line arguments and sets uid/gid, and connects to the database.
db = installation.utils.start_migration(connect=True)

cursor = db.cursor()
cursor.execute("SELECT path FROM repositories")

for path, in cursor:
    pre_receive = os.path.join(path, "hooks", "pre-receive")
    if os.path.isfile(pre_receive):
        os.unlink(pre_receive)
    os.symlink(hook_script, pre_receive)

    post_receive = os.path.join(path, "hooks", "post-receive")
    if os.path.isfile(post_receive):
        print >>sys.stderr, ("WARNING: Moving existing post-receive hook out "
                             "of the way:\n  " + post_receive)
        os.rename(post_receive, post_receive + ".bak")
    os.symlink(hook_script, post_receive)
