import sys

PREFIX = None

def basic():
    import api

    assert PREFIX is not None, "missing argument: --prefix"

    critic = api.critic.startSession()
    repository = api.repository.fetch(critic, name="critic")

    # This set of commits should exist in the repository; each referenced by a
    # branch named PREFIX + letter.
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
    #     L    |
    #     |    J
    #     M

    ALL_LETTERS = "ABCDEFGHIJKLM"

    commits = { letter: api.commit.fetch(repository, ref=PREFIX + letter)
                for letter in ALL_LETTERS + "XY" }

    def make(letters, fn=lambda commits: api.commitset.create(critic, commits)):
        return fn(commits[letter] for letter in letters)
    def tostring(commits):
        return "".join(commit.summary for commit in commits)

    commitset = make(ALL_LETTERS)

    assert isinstance(commitset, api.commitset.CommitSet)
    assert len(commitset) == 13
    assert len(commitset.heads) == 2
    assert commits["J"] in commitset.heads
    assert commits["M"] in commitset.heads
    assert len(commitset.tails) == 2
    assert commits["X"] in commitset.tails
    assert commits["Y"] in commitset.tails

    for commit in make(ALL_LETTERS, list):
        assert commit in commitset

    from_M = commitset.getAncestorsOf(commits["M"], include_self=True)
    from_J = commitset.getAncestorsOf(commits["J"], include_self=True)

    assert len(from_M.heads) == 1
    assert commits["M"] in from_M.heads

    assert len(from_J.heads) == 1
    assert commits["J"] in from_J.heads

    assert tostring(from_M.topo_ordered) == "MLFEDCKHGBA"
    assert tostring(from_J.topo_ordered) == "JIHGBA"

    assert tostring(from_M.date_ordered) == "MLKHGFEDCBA"
    assert tostring(from_J.date_ordered) == "JIHGBA"

    assert commitset.getChildrenOf(commits["A"]) == make("BC", set)
    assert commitset.getChildrenOf(commits["B"]) == make("EG", set)
    assert commitset.getChildrenOf(commits["C"]) == make("D", set)
    assert commitset.getChildrenOf(commits["D"]) == make("E", set)
    assert commitset.getChildrenOf(commits["E"]) == make("F", set)
    assert commitset.getChildrenOf(commits["F"]) == make("L", set)
    assert commitset.getChildrenOf(commits["G"]) == make("H", set)
    assert commitset.getChildrenOf(commits["H"]) == make("KI", set)
    assert commitset.getChildrenOf(commits["I"]) == make("J", set)
    assert commitset.getChildrenOf(commits["J"]) == make("", set)
    assert commitset.getChildrenOf(commits["K"]) == make("L", set)
    assert commitset.getChildrenOf(commits["L"]) == make("M", set)
    assert commitset.getChildrenOf(commits["M"]) == make("", set)
    assert commitset.getChildrenOf(commits["X"]) == make("A", set)
    assert commitset.getChildrenOf(commits["Y"]) == make("G", set)

    assert commitset.getParentsOf(commits["A"]) == make("", list)
    assert commitset.getParentsOf(commits["B"]) == make("A", list)
    assert commitset.getParentsOf(commits["C"]) == make("A", list)
    assert commitset.getParentsOf(commits["D"]) == make("C", list)
    assert commitset.getParentsOf(commits["E"]) == make("DB", list)
    assert commitset.getParentsOf(commits["F"]) == make("E", list)
    assert commitset.getParentsOf(commits["G"]) == make("B", list)
    assert commitset.getParentsOf(commits["H"]) == make("G", list)
    assert commitset.getParentsOf(commits["I"]) == make("H", list)
    assert commitset.getParentsOf(commits["J"]) == make("I", list)
    assert commitset.getParentsOf(commits["K"]) == make("H", list)
    assert commitset.getParentsOf(commits["L"]) == make("FK", list)
    assert commitset.getParentsOf(commits["M"]) == make("L", list)

    assert commitset.getDescendantsOf(commits["A"]) == make("BCDEFGHIJKLM")
    assert commitset.getDescendantsOf(commits["B"]) == make("EFGHIJKLM")
    assert commitset.getDescendantsOf(commits["C"]) == make("DEFLM")
    assert commitset.getDescendantsOf(commits["D"]) == make("EFLM")
    assert commitset.getDescendantsOf(commits["E"]) == make("FLM")
    assert commitset.getDescendantsOf(commits["F"]) == make("LM")
    assert commitset.getDescendantsOf(commits["G"]) == make("HIJKLM")
    assert commitset.getDescendantsOf(commits["H"]) == make("IJKLM")
    assert commitset.getDescendantsOf(commits["I"]) == make("J")
    assert commitset.getDescendantsOf(commits["J"]) == make("")
    assert commitset.getDescendantsOf(commits["K"]) == make("LM")
    assert commitset.getDescendantsOf(commits["L"]) == make("M")
    assert commitset.getDescendantsOf(commits["M"]) == make("")
    assert commitset.getDescendantsOf(commits["X"]) == make("ABCDEFGHIJKLM")
    assert commitset.getDescendantsOf(commits["Y"]) == make("GHIJKLM")
    assert commitset.getDescendantsOf(commits["M"], True) == make("M")
    assert commitset.getDescendantsOf(
        commit for commit in [commits["I"], commits["L"]]) == make("JM")

    assert commitset.getAncestorsOf(commits["A"]) == make("")
    assert commitset.getAncestorsOf(commits["B"]) == make("A")
    assert commitset.getAncestorsOf(commits["C"]) == make("A")
    assert commitset.getAncestorsOf(commits["D"]) == make("AC")
    assert commitset.getAncestorsOf(commits["E"]) == make("ABCD")
    assert commitset.getAncestorsOf(commits["F"]) == make("ABCDE")
    assert commitset.getAncestorsOf(commits["G"]) == make("AB")
    assert commitset.getAncestorsOf(commits["H"]) == make("ABG")
    assert commitset.getAncestorsOf(commits["I"]) == make("ABGH")
    assert commitset.getAncestorsOf(commits["J"]) == make("ABGHI")
    assert commitset.getAncestorsOf(commits["K"]) == make("ABGH")
    assert commitset.getAncestorsOf(commits["L"]) == make("ABCDEFGHK")
    assert commitset.getAncestorsOf(commits["M"]) == make("ABCDEFGHKL")
    assert commitset.getAncestorsOf(commits["A"], True) == make("A")
    assert commitset.getAncestorsOf(
        commit for commit in [commits["D"], commits["G"]]) == make("ABC")

    assert (make("ABC") | make("BCD")) == make("ABCD")
    assert (make("ABC") & make("BCD")) == make("BC")
    assert (make("ABC") - make("BCD")) == make("A")
    assert (make("ABC") ^ make("BCD")) == make("AD")

if __name__ == "__main__":
    import coverage

    for arg in sys.argv[1:]:
        if arg.startswith("--prefix="):
            PREFIX = arg[len("--prefix="):]

    if "basic" in sys.argv[1:]:
        coverage.call("unittest", basic)
