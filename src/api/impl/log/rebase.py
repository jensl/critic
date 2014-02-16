import api

class Rebase(object):
    def __init__(self, review, rebase_id, old_head_id, new_head_id,
                 old_upstream_id, new_upstream_id, creator_id):
        self.review = review
        self.id = rebase_id
        self.old_head_id = old_head_id
        self.new_head_id = new_head_id
        self.old_upstream_id = old_upstream_id
        self.new_upstream_id = new_upstream_id
        self.creator_id = creator_id

        # Fetched on demand.
        self.__old_head = None
        self.__new_head = None
        self.__old_upstream = None
        self.__new_upstream = None
        self.__has_equivalent_merge = None
        self.__equivalent_merge = None
        self.__has_replayed_rebase = None
        self.__replayed_rebase = None
        self.__creator = None

    @property
    def repository(self):
        return self.review.branch.repository

    def getOldHead(self):
        if self.__old_head is None:
            self.__old_head = api.commit.fetch(
                self.repository, commit_id=self.old_head_id)
            if self.new_upstream_id and self.getEquivalentMerge():
                self.__old_head = self.__old_head.parents[0]
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
        if self.__has_equivalent_merge is None:
            critic = self.review.critic
            cursor = critic.getDatabaseCursor()
            cursor.execute(
                """SELECT DISTINCT commits.id, commits.sha1
                     FROM commits
                     JOIN changesets ON (changesets.child=commits.id)
                     JOIN reviewchangesets ON (reviewchangesets.changeset=changesets.id)
                    WHERE reviewchangesets.review=%s
                      AND changesets.type='merge'
                      AND commits.id=%s""",
                (self.review.id, self.old_head_id))
            row = cursor.fetchone()
            if row is None:
                self.__has_equivalent_merge = False
            else:
                self.__has_equivalent_merge = True
                self.__equivalent_merge = api.commit.fetch(
                    self.repository, *row)
        return self.__equivalent_merge

    def getReplayedRebase(self):
        assert self.new_upstream_id is not None
        if self.__has_replayed_rebase is None:
            critic = self.review.critic
            cursor = critic.getDatabaseCursor()
            cursor.execute(
                """SELECT DISTINCT commits.id, commits.sha1
                     FROM commits
                     JOIN changesets ON (changesets.child=commits.id)
                     JOIN reviewchangesets ON (reviewchangesets.changeset=changesets.id)
                    WHERE reviewchangesets.review=%s
                      AND changesets.type='conflicts'
                      AND commits.id=%s""",
                (self.review.id, self.new_head_id))
            row = cursor.fetchone()
            if row is None:
                self.__has_replayed_rebase = False
            else:
                self.__has_replayed_rebase = True
                self.__replayed_rebase = api.commit.fetch(
                    self.repository, *row)
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
