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

from subprocess import Popen as process, check_call, check_output, CalledProcessError, PIPE, STDOUT

def check_input(args, stdin, **kwargs):
    assert isinstance(stdin, str)

    child = process(args, stdin=PIPE, **kwargs)
    stdout, stderr = child.communicate(stdin)

    if child.returncode != 0:
        raise CalledProcessError(child.returncode, args, None)
