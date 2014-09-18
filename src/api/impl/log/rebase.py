import api

class Rebase(object):
    def __init__(self, review, rebase_id, old_head_id, new_head_id,
                 old_upstream_id, new_upstream_id, equivalent_merge_id,
                 replayed_rebase_id, creator_id):
        self.review = review
        self.id = rebase_id
        self.old_head_id = old_head_id
        self.new_head_id = new_head_id
        self.old_upstream_id = old_upstream_id
        self.new_upstream_id = new_upstream_id
        self.equivalent_merge_id = equivalent_merge_id
        self.replayed_rebase_id = replayed_rebase_id
        self.creator_id = creator_id

        # Fetched on demand.
        self.__old_head = None
        self.__new_head = None
        self.__old_upstream = None
        self.__new_upstream = None
        self.__equivalent_merge = None
        self.__replayed_rebase = None
        self.__creator = None

    @property
    def repository(self):
        return self.review.branch.repository

    def getOldHead(self):
        if self.__old_head is None:
            self.__old_head = api.commit.fetch(
                self.repository, commit_id=self.old_head_id)
        return self.__old_head

    def getNewHead(self):
        if self.__new_head is None:
            self.__new_head = api.commit.fetch(
                self.repository, commit_id=self.new_head_id)
        return self.__new_head

    def getOldUpstream(self):
        if self.__old_upstream is None:
            self.__old_upstream = api.commit.fetch(
                self.repository, commit_id=self.old_upstream_id)
        return self.__old_upstream

    def getNewUpstream(self):
        if self.__new_upstream is None:
            self.__new_upstream = api.commit.fetch(
                self.repository, commit_id=self.new_upstream_id)
        return self.__new_upstream

    def getEquivalentMerge(self):
        assert self.new_upstream_id is not None
        if self.equivalent_merge_id is None:
            return None
        if self.__equivalent_merge is None:
            self.__equivalent_merge = api.commit.fetch(
                self.repository, commit_id=self.equivalent_merge_id)
        return self.__equivalent_merge

    def getReplayedRebase(self):
        assert self.new_upstream_id is not None
        if self.replayed_rebase_id is None:
            return None
        if self.__replayed_rebase is None:
            self.__replayed_rebase = api.commit.fetch(
                self.repository, commit_id=self.replayed_rebase_id)
        return self.__replayed_rebase

    def getCreator(self, critic):
        if self.__creator is None:
            self.__creator = api.user.fetch(critic, user_id=self.creator_id)
        return self.__creator

    def wrap(self, critic):
        if self.new_upstream_id is None:
            return api.log.rebase.HistoryRewrite(critic, self)
        else:
            return api.log.rebase.MoveRebase(critic, self)
