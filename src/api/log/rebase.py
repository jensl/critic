import api

class RebaseError(api.APIError):
    """Base exception for all errors related to the Rebase class"""
    pass

class InvalidRebaseId(RebaseError):
    """Raised when an invalid rebase id is used"""

    def __init__(self, value):
        """Constructor"""
        super(InvalidRebaseId, self).__init__("Invalid rebase id: %r" % value)
        self.value = value

class Rebase(api.APIObject):
    """Representation of a rebase of a review branch"""

    @property
    def id(self):
        return self._impl.id

    @property
    def review(self):
        return self._impl.getReview(self.critic)

    @property
    def old_head(self):
        return self._impl.getOldHead(self.critic)

    @property
    def new_head(self):
        return self._impl.getNewHead(self.critic)

    @property
    def creator(self):
        return self._impl.getCreator(self.critic)

class HistoryRewrite(Rebase):
    """Representation of a history rewrite rebase

       The review branch after a history rewrite rebase is always based on the
       same upstream commit as before it and makes the exact same changes
       relative it, but contains a different set of actual commits."""

    pass

class MoveRebase(Rebase):
    """Representation of a "move" rebase

       A move rebase moves the changes in the review onto a different upstream
       commit."""

    @property
    def old_upstream(self):
        return self._impl.getOldUpstream(self.critic)

    @property
    def new_upstream(self):
        return self._impl.getNewUpstream(self.critic)

    @property
    def equivalent_merge(self):
        return self._impl.getEquivalentMerge(self.critic)

    @property
    def replayed_rebase(self):
        return self._impl.getReplayedRebase(self.critic)

def fetch(critic, rebase_id):
    """Fetch a Rebase object with the given id"""
    import api.impl
    assert isinstance(critic, api.critic.Critic)
    return api.impl.log.rebase.fetch(critic, rebase_id)

def fetchAll(critic, review=None):
    """Fetch Rebase objects for all rebases

       If a review is provided, restrict the return value to rebases of the
       specified review."""
    import api.impl
    assert isinstance(critic, api.critic.Critic)
    assert review is None or isinstance(review, api.review.Review)
    return api.impl.log.rebase.fetchAll(critic, review)
