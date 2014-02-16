import api

class FilterError(api.APIError):
    """Base exception for all errors related to the User class."""
    pass

class Filter(api.APIObject):
    """Base class of RepositoryFilter and ReviewFilter"""

    @property
    def subject(self):
        """The filter's subject

           The subject is the user that the filter applies to."""
        return self._impl.getSubject(self.critic)

    @property
    def type(self):
        """The filter's type

           The type is always one of "reviewer", "watcher" and "ignore"."""
        return self._impl.type

    @property
    def path(self):
        """The filter's path"""
        return self._impl.path

class RepositoryFilter(Filter):
    """Representation of a repository filter

       A repository filter is a filter that applies to all reviews in a
       repository."""

    @property
    def id(self):
        """The repository filter's unique id"""
        return self._impl.id

    @property
    def repository(self):
        """The repository filter's repository"""
        return self._impl.getRepository(self.critic)

    @property
    def delegates(self):
        """The repository filter's delegates, or None

           The delegates are returned as a frozenset of api.user.User objects.
           If the filter's type is not "reviewer", this attribute's value is
           None."""
        return self._impl.getDelegates(self.critic)

    @property
    def json(self):
        """A dictionary suitable for JSON encoding"""
        return { "id": self.id,
                 "subject": self.subject.json,
                 "type": self.type,
                 "path": self.path,
                 "delegates": ([delegate.json for delegate in self.delegates]
                               if self.delegates else None) }

class ReviewFilter(Filter):
    """Representation of a review filter

       A review filter is a filter that applies to a single review only."""

    @property
    def id(self):
        """The review filter's unique id"""
        return self._impl.id

    @property
    def review(self):
        """The review filter's review"""
        return self._impl.getReview(self.critic)

    @property
    def creator(self):
        """The review filter's creator

           This is the user that created the review filter, which can be
           different from the filter's subject."""
        return self._impl.getCreator(self.critic)

    @property
    def json(self):
        """A dictionary suitable for JSON encoding"""
        return { "id": self.id,
                 "subject": self.subject.json,
                 "type": self.type,
                 "path": self.path,
                 "creator": self.creator.json }
