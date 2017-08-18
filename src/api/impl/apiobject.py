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

    @classmethod
    def create(Implementation, critic, *args):
        return Implementation(*args).wrap(critic)

    @classmethod
    def make(Implementation, critic, args_list, ignored_errors=()):
        for args in args_list:
            cache_key = args[0]
            try:
                item = critic._impl.lookup(Implementation, cache_key)
            except KeyError:
                try:
                    item = Implementation.create(critic, *args)
                except ignored_errors:
                    continue

                critic._impl.assign(Implementation, cache_key, item)

            yield item

    @classmethod
    def cached(Implementation, InvalidIdError=None):
        def wrap(fetch):
            def wrapper(critic, item_id, *args):
                if item_id is not None:
                    try:
                        return critic._impl.lookup(Implementation, item_id)
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
                    cache = critic._impl.lookup(Implementation)
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
        return critic._impl.lookup(Implementation)

    @staticmethod
    def refresh(critic, tables, cached_objects):
        """Refresh objects after transaction commit

           The |tables| parameter is a set of database tables that were modified
           in the transaction. The |cached_objects| parameter is a dictionary
           mapping object ids to cached objects (wrappers) of this type."""
        pass

    @classmethod
    def updateAll(Implementation, critic, query, cached_objects):
        """Execute the query and update all cached objects

           The query must take a single parameter, which is a list of object
           ids. It will be executed with the list of ids of all cached
           objects. Each returned row must have the id of the object as the
           first item, and the implementation constructor must take the row
           as a whole as arguments:

             new_impl = Implementation(*row)"""
        cursor = critic.getDatabaseCursor()
        cursor.execute(query, (cached_objects.keys(),))
        for row in cursor:
            cached_objects[row[0]]._set_impl(Implementation(*row))
