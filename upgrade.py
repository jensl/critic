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

if __name__ == "__main__":
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

    from installation import upgrade_main

    upgrade_main.main()
