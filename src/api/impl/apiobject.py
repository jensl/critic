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
    def make(Implementation, critic, args_list, ignored_errors=()):
        for args in args_list:
            cache_key = args[0]
            try:
                item = critic._impl.lookup(
                    Implementation.wrapper_class, cache_key)
            except KeyError:
                try:
                    item = Implementation.create(critic, *args)
                except ignored_errors:
                    continue

                critic._impl.assign(
                    Implementation.wrapper_class, cache_key, item)

            yield item

    @classmethod
    def cached(Implementation):
        def wrap(fetch):
            def wrapper(critic, item_id, *args):
                if item_id is not None:
                    try:
                        return critic._impl.lookup(Implementation.wrapper_class,
                                                   item_id)
                    except KeyError:
                        pass
                return fetch(critic, item_id, *args)
            return wrapper
        return wrap
