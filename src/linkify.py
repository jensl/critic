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

import re

ALL_LINKTYPES = []

class Context(object):
    def __init__(self, db=None, request=None, repository=None, review=None, **kwargs):
        self.db = db
        self.request = request
        self.repository = repository or (review.repository if review else None)
        self.review = review
        self.extra = kwargs

class LinkType(object):
    """
    A link type object is responsible for providing a regexp fragment
    that matches the words (or substrings) that the link type produces
    hyper-links from, and for constructing actual URLs from such
    words.
    """

    def __init__(self, fragment):
        """
        LinkType(regexp) -> link type object

        Create a link type object and add it to the global list of
        link type objects.  The 'fragment' argument should be a string
        containing a regexp fragment without captures suitable to
        insert into the complete regexp

          (?:^|\b)(wordA|wordB|...)(?:\b|$)

        which is then used to split text into "words" which are
        individually turned into links or left as-is.
        """

        self.fragment = fragment
        self.fragment_regexp = re.compile("%s$" % fragment)

        ALL_LINKTYPES.append(self)

    def match(self, word):
        return bool(self.fragment_regexp.match(word))

    def linkify(self, word):
        """
        linkify(word) -> None or a string.

        If the whole word matches what this link type handles,
        constructs a URL to which this word should be made a link,
        otherwise returns None.  Implementations should expect to be
        called with words that don't match what they handle.

        Sub-classes must override this method.
        """
        pass

class SimpleLinkType(LinkType):
    """
    Base class for link type when the word contains the URL.
    """

    def __init__(self, fragment, regexp=None):
        super(SimpleLinkType, self).__init__(fragment)
        if isinstance(regexp, str):
            self.regexp = re.compile(regexp)
        else:
            self.regexp = regexp

    def linkify(self, word, context):
        if self.regexp:
            return self.regexp.match(word).group(1)
        else:
            return word

class HTTP(SimpleLinkType):
    """
    Link type "plain URL string".
    """

    def __init__(self):
        super(HTTP, self).__init__("https?://\\S+[^\\s.,:;!?)]")

class URL(SimpleLinkType):
    """
    Link type <URL:...>.
    """

    def __init__(self):
        super(URL, self).__init__("<URL:[^>]+>", "<URL:([^>]+)>$")

class SHA1(LinkType):
    """
    SHA-1 link type.

    Converts SHA-1 sums in text (either full or abbreviated) into
    links to the diff of the referenced commit.  When processed in the
    context of a repository, a matching commit in that repository is
    preferred (assuming it exists.)  When processed in the context of
    a review, a 'review=<id>' parameter is appended to the URL, which
    links to the diff of the referenced commit in the context of the
    review (which includes comments and allows reviewing.)
    """

    def __init__(self):
        super(SHA1, self).__init__("[0-9A-Fa-f]{8,40}")

    def linkify(self, word, context):
        sha1 = word
        if context.repository \
                and context.repository.iscommit(word):
            sha1 = context.repository.revparse(sha1)
            if context.review \
                    and context.review.containsCommit(context.db, sha1):
                return "/%s/%s?review=%d" % (context.repository.name, sha1, context.review.id)
            else:
                return "/%s/%s" % (context.repository.name, sha1)
        else:
            return "/%s" % sha1

class Diff(LinkType):
    """
    Diff link type.

    Like the SHA-1 link type, but with two sums separated by '..', and
    links to the diff between the two referenced commits.
    """

    def __init__(self):
        super(Diff, self).__init__("[0-9A-Fa-f]{8,40}\\.\\.[0-9A-Fa-f]{8,40}")

    def linkify(self, word, context):
        from_sha1, _, to_sha1 = word.partition("..")
        if context.repository \
                and context.repository.iscommit(from_sha1) \
                and context.repository.iscommit(to_sha1):
            from_sha1 = context.repository.revparse(from_sha1)
            to_sha1 = context.repository.revparse(to_sha1)
            if context.review \
                    and context.review.containsCommit(context.db, from_sha1) \
                    and context.review.containsCommit(context.db, to_sha1):
                return "/%s/%s..%s?review=%d" % (context.repository.name, from_sha1, to_sha1, context.review.id)
            else:
                return "/%s/%s..%s" % (context.repository.name, from_sha1, to_sha1)
        else:
            return "/%s..%s" % (from_sha1, to_sha1)

class Review(LinkType):
    """
    Review link type.

    Converts 'r/<id>' in text into a link to the front-page of the
    corresponding review.
    """

    def __init__(self):
        super(Review, self).__init__("r/\\d+")

    def linkify(self, word, context):
        return "/" + word

HTTP()
URL()
Diff()
SHA1()
Review()

try: import customization.linktypes
except ImportError: pass
