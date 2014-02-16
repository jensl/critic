import api

class Partition(object):
    def __init__(self, commits):
        assert not commits or len(commits.heads) == 1

        self.commits = commits
        self.preceding = None
        self.following = None

    def wrap(self, critic):
        return api.log.partition.Partition(critic, self)

def create(critic, commits, rebases):
    commits = api.commitset.create(critic, commits)
    partitions = []

    def add(rebase, partition):
        if partitions:
            previous_rebase, previous_partition = partitions[-1]
            previous_partition._impl.preceding = \
                api.log.partition.Partition.Edge(previous_rebase, partition)
            partition._impl.following = \
                api.log.partition.Partition.Edge(previous_rebase,
                                                 previous_partition)
        partitions.append((rebase, partition))

    rebase = None

    for rebase in reversed(rebases):
        partition_commits = commits.getAncestorsOf(
            rebase.old_head, rebase.old_head in commits)
        commits = commits - partition_commits
        add(rebase, Partition(partition_commits).wrap(critic))

    if len(commits.heads) > 1:
        raise api.log.partition.PartitionError(
            "Incompatible commits/rebases arguments")

    add(None, Partition(commits).wrap(critic))

    return partitions[-1][1]
