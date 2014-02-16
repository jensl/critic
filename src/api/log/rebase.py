import api

class Rebase(api.APIObject):
    """Representation of a rebase of a review branch"""

    @property
    def id(self):
        return self._impl.id

    @property
    def review(self):
        return self._impl.review

    @property
    def old_head(self):
        return self._impl.getOldHead()

    @property
    def new_head(self):
        return self._impl.getNewHead()

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
        return self._impl.getOldUpstream()

    @property
    def new_upstream(self):
        return self._impl.getNewUpstream()

    @property
    def equivalent_merge(self):
        return self._impl.getEquivalentMerge()

    @property
    def replayed_rebase(self):
        return self._impl.getReplayedRebase()
