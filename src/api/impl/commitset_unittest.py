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
    #     M    |
    #     |    J
    #     N
    #     |
    #     L

    ALL_LETTERS = "ABCDEFGHIJKLMN"

    commits = { letter: api.commit.fetch(repository, ref=PREFIX + letter)
                for letter in ALL_LETTERS + "XY" }

    def make(letters, fn=lambda commits: api.commitset.create(critic, commits)):
        return fn(commits[letter] for letter in letters)
    def tostring(commits):
        return "".join(commit.summary for commit in commits)

    commitset = make(ALL_LETTERS)

    assert isinstance(commitset, api.commitset.CommitSet)
    assert len(commitset) == 14
    assert len(commitset.heads) == 2
    assert commits["J"] in commitset.heads
    assert commits["L"] in commitset.heads
    assert len(commitset.tails) == 2
    assert commits["X"] in commitset.tails
    assert commits["Y"] in commitset.tails

    for commit in make(ALL_LETTERS, list):
        assert commit in commitset

    from_L = commitset.getAncestorsOf(commits["L"], include_self=True)
    from_J = commitset.getAncestorsOf(commits["J"], include_self=True)

    assert len(from_L.heads) == 1
    assert commits["L"] in from_L.heads

    assert len(from_J.heads) == 1
    assert commits["J"] in from_J.heads

    assert tostring(from_L.topo_ordered) == "LNMFEDCKHGBA"
    assert tostring(from_J.topo_ordered) == "JIHGBA"

    assert tostring(from_L.date_ordered) == "LNMKHGFEDCBA"
    assert tostring(from_J.date_ordered) == "JIHGBA"

    assert commitset.getChildrenOf(commits["A"]) == make("BC", set)
    assert commitset.getChildrenOf(commits["B"]) == make("EG", set)
    assert commitset.getChildrenOf(commits["C"]) == make("D", set)
    assert commitset.getChildrenOf(commits["D"]) == make("E", set)
    assert commitset.getChildrenOf(commits["E"]) == make("F", set)
    assert commitset.getChildrenOf(commits["F"]) == make("M", set)
    assert commitset.getChildrenOf(commits["G"]) == make("H", set)
    assert commitset.getChildrenOf(commits["H"]) == make("KI", set)
    assert commitset.getChildrenOf(commits["I"]) == make("J", set)
    assert commitset.getChildrenOf(commits["J"]) == make("", set)
    assert commitset.getChildrenOf(commits["K"]) == make("M", set)
    assert commitset.getChildrenOf(commits["L"]) == make("", set)
    assert commitset.getChildrenOf(commits["M"]) == make("N", set)
    assert commitset.getChildrenOf(commits["N"]) == make("L", set)
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
    assert commitset.getParentsOf(commits["L"]) == make("N", list)
    assert commitset.getParentsOf(commits["M"]) == make("FK", list)
    assert commitset.getParentsOf(commits["N"]) == make("M", list)

    assert commitset.getDescendantsOf(commits["A"]) == make("BCDEFGHIJKLMN")
    assert commitset.getDescendantsOf(commits["B"]) == make("EFGHIJKLMN")
    assert commitset.getDescendantsOf(commits["C"]) == make("DEFLMN")
    assert commitset.getDescendantsOf(commits["D"]) == make("EFLMN")
    assert commitset.getDescendantsOf(commits["E"]) == make("FLMN")
    assert commitset.getDescendantsOf(commits["F"]) == make("LMN")
    assert commitset.getDescendantsOf(commits["G"]) == make("HIJKLMN")
    assert commitset.getDescendantsOf(commits["H"]) == make("IJKLMN")
    assert commitset.getDescendantsOf(commits["I"]) == make("J")
    assert commitset.getDescendantsOf(commits["J"]) == make("")
    assert commitset.getDescendantsOf(commits["K"]) == make("LMN")
    assert commitset.getDescendantsOf(commits["L"]) == make("")
    assert commitset.getDescendantsOf(commits["M"]) == make("NL")
    assert commitset.getDescendantsOf(commits["N"]) == make("L")
    assert commitset.getDescendantsOf(commits["X"]) == make("ABCDEFGHIJKLMN")
    assert commitset.getDescendantsOf(commits["Y"]) == make("GHIJKLMN")
    assert commitset.getDescendantsOf(commits["L"], True) == make("L")
    assert commitset.getDescendantsOf(
        commit for commit in [commits["I"], commits["N"]]) == make("JL")

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
    assert commitset.getAncestorsOf(commits["L"]) == make("ABCDEFGHKMN")
    assert commitset.getAncestorsOf(commits["M"]) == make("ABCDEFGHK")
    assert commitset.getAncestorsOf(commits["N"]) == make("ABCDEFGHKM")
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
