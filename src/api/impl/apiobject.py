# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2015 the Critic contributors, Opera Software ASA
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

class APIObject(object):
    def wrap(self, critic):
        return self.wrapper_class(critic, self)

    def refresh(self, critic):
        return self

    @classmethod
    def create(Implementation, critic, *args):
        return Implementation(*args).wrap(critic)

    @classmethod
    def make(Implementation, critic, args_list):
        for args in args_list:
            object_id = args[0]
            yield critic._impl.cached(
                Implementation.wrapper_class, object_id,
                lambda: Implementation.create(critic, *args))
