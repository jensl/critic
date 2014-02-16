import api

class Branch(object):
    def __init__(self, branch_id, name, repository_id, head_id, repository=None):
        self.id = branch_id
        self.name = name
        self.__repository_id = repository_id
        self.__head_id = head_id
        self.__head = None
        self.__commits = None

    def getRepository(self, critic):
        return api.repository.fetch(critic, repository_id=self.__repository_id)

    def getHead(self, critic):
        if self.__head is None:
            self.__head = api.commit.fetch(
                self.getRepository(critic), commit_id=self.__head_id)
        return self.__head

    def getCommits(self, critic):
        if self.__commits is None:
            repository = self.getRepository(critic)
            cursor = critic.getDatabaseCursor()
            cursor.execute("""SELECT commit
                                FROM reachable
                               WHERE branch=%s""",
                           (self.id,))
            self.__commits = api.commitset.create(
                critic, (api.commit.fetch(repository, commit_id)
                         for (commit_id,) in cursor))
        return self.__commits

    def wrap(self, critic):
        return api.branch.Branch(critic, self)

def fetch(critic, branch_id, repository, name):
    cursor = critic.getDatabaseCursor()
    if branch_id is not None:
        cursor.execute("""SELECT id, name, repository, head
                            FROM branches
                           WHERE id=%s""",
                       (branch_id,))
        row = cursor.fetchone()
        if not row:
            raise api.branch.InvalidBranchId(branch_id)
    else:
        cursor.execute("""SELECT id, name, repository, head
                            FROM branches
                           WHERE repository=%s
                             AND name=%s""",
                       (repository.id, name,))
        row = cursor.fetchone()
        if not row:
            raise api.branch.InvalidBranchName(name)
    branch_id, name, repository_id, head_id = row

    def callback():
        return Branch(branch_id, name, repository_id, head_id,
                      repository=repository).wrap(critic)

    return critic._impl.cached(api.branch.Branch, branch_id, callback)
