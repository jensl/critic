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
    def cached(Implementation, InvalidIdError=None):
        def wrap(fetch):
            def wrapper(critic, item_id, *args):
                if item_id is not None:
                    try:
                        return critic._impl.lookup(Implementation.wrapper_class,
                                                   item_id)
                    except KeyError:
                        pass
                result = fetch(critic, item_id, *args)
                if InvalidIdError is None:
                    return result
                try:
                    return next(result)
                except StopIteration:
                    raise InvalidIdError(item_id)
            return wrapper
        return wrap

    @classmethod
    def cachedMany(Implementation, InvalidIdsError):
        def wrap(fetchMany):
            def wrapper(critic, item_ids):
                items = {}
                try:
                    cache = critic._impl.lookup(Implementation.wrapper_class)
                except KeyError:
                    cache = {}
                uncached_ids = set(item_ids) - set(cache.keys())
                items = {item_id: cache[item_id]
                         for item_id in item_ids
                         if item_id in cache}
                if uncached_ids:
                    items.update(
                        (item.id, item)
                        for item in fetchMany(critic, list(uncached_ids)))
                if len(items) < len(set(item_ids)):
                    invalid_ids = sorted(set(item_ids) - set(items.keys()))
                    raise InvalidIdsError(invalid_ids)
                return [items[item_id] for item_id in item_ids]
            return wrapper
        return wrap

    @classmethod
    def allCached(Implementation, critic):
        """Return all cached objects of this type

           The cached objects are returned as a dictionary mapping the object id
           to the object. This dictionary should not be modified."""
        # Don't catch KeyError here. Something is probably wrong if this
        # function is called when no objects of the type are cached.
        return critic._impl.lookup(Implementation.wrapper_class)
