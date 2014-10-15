# @dependency 001-main/002-createrepository.py

import os
import time

with repository.workcopy() as work:
    REMOTE_URL = instance.repository_url("alice")

    os.mkdir(os.path.join(work.path, "009-commitset"))

    # Generate this set of commits:
    #
    #  (X)
    #   |
    #   A
    #  / \
    # C   B  (Y)
    # |   |\ /
    # D   | G
    #  \ /  |
    #   E   H
    #   |   |\
    #   F   K \
    #    \ /   I
    #     M    |
    #     |    J
    #     N
    #     |
    #     L
    #
    # Commits are named in (committer date) chronological order; A is oldest, M
    # is youngest.  X and Y are the tails of the set.

    commits = {}
    timestamp = int(time.time()) - 3600

    def commit(letter, delta=0):
        global timestamp
        filename = os.path.join(work.path, "009-commitset", letter)
        with open(filename, "w") as file:
            print >>file, letter
        work.run(["add", os.path.join("009-commitset", letter)])
        work.run(["commit", "-m" + letter],
                 GIT_COMMITTER_DATE="%d +0000" % (timestamp + delta))
        timestamp += 10
        commits[letter] = work.run(["rev-parse", "HEAD"]).strip()

    def merge(letter, what, delta=0):
        global timestamp
        work.run(["merge", "-m" + letter, what],
                 GIT_COMMITTER_DATE="%d +0000" % (timestamp + delta))
        timestamp += 10
        commits[letter] = work.run(["rev-parse", "HEAD"]).strip()

    work.run(["checkout", "-b", "X"])
    commit("X")

    work.run(["checkout", "-b", "Y"])
    commit("Y")

    work.run(["checkout", "-b", "ACD", "X"])
    commit("A")

    work.run(["checkout", "-b", "B"])
    commit("B")

    work.run(["checkout", "ACD"])
    commit("C")
    commit("D")

    work.run(["checkout", "-b", "EF"])
    merge("E", "B")
    commit("F")

    work.run(["checkout", "-b", "GHK", commits["B"]])
    merge("G", "Y")
    commit("H")

    work.run(["checkout", "-b", "IJ"])
    commit("I")
    commit("J")

    work.run(["checkout", "GHK"])
    commit("K")

    work.run(["checkout", "-b", "MNL", commits["F"]])
    merge("M", "GHK", delta=10)
    commit("N", delta=10)
    commit("L", delta=-20)

    work.run(["push", REMOTE_URL] +
             ["%s:refs/heads/009-commitset/%s" % (sha1, letter)
              for letter, sha1 in commits.items()])

    try:
        instance.unittest("api.commitset", ["basic"],
                          args=["--prefix=009-commitset/"])
    finally:
        work.run(["push", REMOTE_URL] +
                 [":refs/heads/009-commitset/%s" % letter
                  for letter in commits.keys()])
