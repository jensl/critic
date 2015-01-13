import api

class Rebase(object):
    def __init__(self, rebase_id, review_id, creator_id,
                 old_head_id, new_head_id, old_upstream_id, new_upstream_id,
                 equivalent_merge_id, replayed_rebase_id):
        self.id = rebase_id
        self.review_id = review_id
        self.old_head_id = old_head_id
        self.new_head_id = new_head_id
        self.old_upstream_id = old_upstream_id
        self.new_upstream_id = new_upstream_id
        self.equivalent_merge_id = equivalent_merge_id
        self.replayed_rebase_id = replayed_rebase_id
        self.creator_id = creator_id

    def getReview(self, critic):
        return api.review.fetch(critic, review_id=self.review_id)

    def getRepository(self, critic):
        return self.getReview(critic).branch.repository

    def getOldHead(self, critic):
        return api.commit.fetch(self.getRepository(critic),
                                commit_id=self.old_head_id)

    def getNewHead(self, critic):
        return api.commit.fetch(self.getRepository(critic),
                                commit_id=self.new_head_id)

    def getOldUpstream(self, critic):
        return api.commit.fetch(self.getRepository(critic),
                                commit_id=self.old_upstream_id)

    def getNewUpstream(self, critic):
        return api.commit.fetch(self.getRepository(critic),
                                commit_id=self.new_upstream_id)

    def getEquivalentMerge(self, critic):
        assert self.new_upstream_id is not None
        if self.equivalent_merge_id is None:
            return None
        return api.commit.fetch(self.getRepository(critic),
                                commit_id=self.equivalent_merge_id)

    def getReplayedRebase(self, critic):
        assert self.new_upstream_id is not None
        if self.replayed_rebase_id is None:
            return None
        return api.commit.fetch(self.getRepository(critic),
                                commit_id=self.replayed_rebase_id)

    def getCreator(self, critic):
        return api.user.fetch(critic, user_id=self.creator_id)

    def wrap(self, critic):
        if self.new_upstream_id is None:
            return api.log.rebase.HistoryRewrite(critic, self)
        else:
            return api.log.rebase.MoveRebase(critic, self)

def make(critic, args):
    for (rebase_id, review_id, creator_id,
         old_head_id, new_head_id, old_upstream_id, new_upstream_id,
         equivalent_merge_id, replayed_rebase_id) in args:
        def callback():
            return Rebase(
                rebase_id, review_id, creator_id,
                old_head_id, new_head_id, old_upstream_id, new_upstream_id,
                equivalent_merge_id, replayed_rebase_id).wrap(critic)
        yield critic._impl.cached(api.log.rebase.Rebase, rebase_id, callback)

def fetch(critic, rebase_id):
    cursor = critic.getDatabaseCursor()
    cursor.execute(
        """SELECT id, review, uid,
                  old_head, new_head, old_upstream, new_upstream,
                  equivalent_merge, replayed_rebase
             FROM reviewrebases
            WHERE id=%s
              AND new_head IS NOT NULL""",
        (rebase_id,))
    try:
        return next(make(critic, cursor))
    except StopIteration:
        raise api.log.rebase.InvalidRebaseId(rebase_id)

def fetchAll(critic, review):
    cursor = critic.getDatabaseCursor()
    if review is not None:
        cursor.execute(
            """SELECT id, review, uid,
                      old_head, new_head, old_upstream, new_upstream,
                      equivalent_merge, replayed_rebase
                 FROM reviewrebases
                WHERE review=%s
                  AND new_head IS NOT NULL
             ORDER BY id DESC""",
            (review.id,))
    else:
        cursor.execute(
            """SELECT id, review, uid,
                      old_head, new_head, old_upstream, new_upstream,
                      equivalent_merge, replayed_rebase
                 FROM reviewrebases
                WHERE new_head IS NOT NULL
             ORDER BY id DESC""")
    return list(make(critic, cursor))
