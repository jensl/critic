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

import api

class ReplyError(api.APIError):
    pass

class InvalidReplyId(ReplyError):
    """Raised when an invalid reply id is used."""

    def __init__(self, reply_id):
        """Constructor"""
        super(InvalidReplyId, self).__init__(
            "Invalid reply id: %d" % reply_id)
        self.reply_id = reply_id

class InvalidReplyIds(ReplyError):
    """Raised by fetchMany() when invalid reply ids are used."""

    def __init__(self, reply_ids):
        """Constructor"""
        super(InvalidReplyIds, self).__init__(
            "Invalid reply ids: %s" % ", ".join(map(str, reply_ids)))
        self.reply_ids = reply_ids

class Reply(api.APIObject):
    @property
    def id(self):
        """The reply's unique id"""
        return self._impl.id

    @property
    def is_draft(self):
        """True if the reply is not yet published

           Unpublished replies are not displayed to other users."""
        return self._impl.is_draft

    @property
    def comment(self):
        """The comment this reply is a reply to

           The comment is returned as an api.comment.Comment object."""
        return self._impl.getComment(self.critic)

    @property
    def author(self):
        """The reply's author

           The author is returned as an api.user.User object."""
        return self._impl.getAuthor(self.critic)

    @property
    def timestamp(self):
        """The reply's timestamp

           The return value is a datetime.datetime object."""
        return self._impl.timestamp

    @property
    def text(self):
        """The reply's text"""
        return self._impl.text

def fetch(critic, reply_id):
    """Fetch the Reply object with the given id"""
    import api.impl
    assert isinstance(critic, api.critic.Critic)
    assert isinstance(reply_id, int)
    return api.impl.reply.fetch(critic, reply_id)

def fetchMany(critic, reply_ids):
    """Fetch multiple Reply objects with the given ids"""
    import api.impl
    assert isinstance(critic, api.critic.Critic)
    reply_ids = list(reply_ids)
    assert all(isinstance(reply_id, int) for reply_id in reply_ids)
    return api.impl.reply.fetchMany(critic, reply_ids)
