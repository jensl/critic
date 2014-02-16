import sys

def basic():
    import api

    critic = api.critic.startSession()
    review = api.review.fetch(critic, review_id=1)

    assert isinstance(review, api.review.Review)

    assert isinstance(review.id, int)
    assert review.id == 1
    assert int(review) == 1

    assert api.review.fetch(critic, branch=review.branch) is review

    assert isinstance(review.summary, basestring)
    assert review.summary == "Minor /dashboard query optimizations"

    assert review.description is None

    assert isinstance(review.branch, api.branch.Branch)
    assert review.branch.name == "r/004-createreview"
    assert review.branch.repository.name == "critic"

    assert isinstance(review.owners, frozenset)
    assert all(isinstance(owner, api.user.User) for owner in review.owners)
    assert list(review.owners)[0].name == "alice"

    assert isinstance(review.filters, list)
    assert all(isinstance(review_filter, api.filters.ReviewFilter)
               for review_filter in review.filters)
    assert len(review.filters) == 3

    assert isinstance(review.filters[0].subject, api.user.User)
    assert review.filters[0].subject.name == "bob"
    assert review.filters[0].type == "reviewer"
    assert review.filters[0].path == "/"
    assert isinstance(review.filters[0].id, int)
    assert review.filters[0].review is review
    assert isinstance(review.filters[0].creator, api.user.User)
    assert review.filters[0].creator.name == "alice"
    assert isinstance(review.filters[0].json, dict)

    assert isinstance(review.filters[1].subject, api.user.User)
    assert review.filters[1].subject.name == "dave"
    assert review.filters[1].type == "watcher"
    assert review.filters[1].path == "/"
    assert isinstance(review.filters[1].id, int)
    assert review.filters[1].id != review.filters[0].id
    assert review.filters[1].review is review
    assert isinstance(review.filters[1].creator, api.user.User)
    assert review.filters[1].creator.name == "alice"
    assert isinstance(review.filters[1].json, dict)

    assert isinstance(review.filters[2].subject, api.user.User)
    assert review.filters[2].subject.name == "erin"
    assert review.filters[2].type == "watcher"
    assert review.filters[2].path == "/"
    assert isinstance(review.filters[2].id, int)
    assert review.filters[2].id not in (review.filters[0].id,
                                        review.filters[1].id)
    assert review.filters[2].review is review
    assert isinstance(review.filters[2].creator, api.user.User)
    assert review.filters[2].creator.name == "alice"
    assert isinstance(review.filters[2].json, dict)

    assert isinstance(review.commits, api.commitset.CommitSet)
    assert all(isinstance(commit, api.commit.Commit)
               for commit in review.commits)
    assert len(review.commits) == 2
    assert len(review.commits.heads) == 1
    assert len(review.commits.tails) == 1
    topo_ordered = review.commits.topo_ordered
    assert topo_ordered.next().summary == "Add missing import"
    assert topo_ordered.next().summary == "Minor /dashboard query optimizations"
    assert review.commits == review.branch.commits

    assert isinstance(review.rebases, list)
    assert len(review.rebases) == 0

    try:
        api.review.fetch(critic, review_id=10000)
    except api.review.InvalidReviewId:
        pass
    except Exception as error:
        assert False, "wrong exception raised: %s" % error
    else:
        assert False, "no exception raised"

    master = api.branch.fetch(
        critic, repository=review.branch.repository, name="master")

    try:
        api.review.fetch(critic, branch=master)
    except api.review.InvalidReviewBranch:
        pass
    except Exception as error:
        assert False, "wrong exception raised: %s" % error
    else:
        assert False, "no exception raised"

if __name__ == "__main__":
    import coverage

    if "basic" in sys.argv[1:]:
        coverage.call("unittest", basic)
