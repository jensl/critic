TEST_NAME = "030-trackingreview"
BRANCH_NAME = [TEST_NAME + "-1",
               TEST_NAME + "-2"]
UPSTREAM_NAME = [name + "-upstream"
                 for name in BRANCH_NAME]
SUMMARY = TEST_NAME

ORIGINAL_SHA1 = "37bfd1ee7d301b364d0a8c716e9bca36efd5d139"
REVIEWED_SHA1 = []
UPSTREAM_SHA1 = ["22afd9377add956e1e8d8dd6efa378fad9237532",
                 "702c1b1a4043d8837e788317698cfc88c5570ff8"]

def to(name):
    return testing.mailbox.ToRecipient("%s@example.org" % name)

def about(subject):
    return testing.mailbox.WithSubject(subject)

repository.run(["branch", UPSTREAM_NAME[0], UPSTREAM_SHA1[0]])
repository.run(["branch", UPSTREAM_NAME[1], UPSTREAM_SHA1[1]])

with repository.workcopy() as work:
    work.run(["checkout", "-b", BRANCH_NAME[0], UPSTREAM_SHA1[0]])
    work.run(["cherry-pick", ORIGINAL_SHA1])
    work.run(["push", "origin", "HEAD"])

    REVIEWED_SHA1.append(work.run(["rev-parse", "HEAD"]).strip())

    work.run(["checkout", "-b", BRANCH_NAME[1], UPSTREAM_SHA1[1]])
    work.run(["cherry-pick", ORIGINAL_SHA1])
    work.run(["push", "origin", "HEAD"])

    REVIEWED_SHA1.append(work.run(["rev-parse", "HEAD"]).strip())

with_class = testing.expect.with_class
extract_text = testing.expect.extract_text

def check_tracking(branch_name, disabled=False):
    def check(document):
        class_names = ["tracking"]
        if disabled:
            class_names.append("disabled")
        p_tracking = document.find("p", attrs=with_class(*class_names))
        testing.expect.check("tracking", extract_text(p_tracking))
        if not disabled:
            testing.expect.check("tracking", p_tracking["class"])

        code_branch = document.findAll("code", attrs=with_class("branch"))
        testing.expect.check(2, len(code_branch))
        testing.expect.check(branch_name, extract_text(code_branch[1]))

        code_repository = document.findAll("code", attrs=with_class("repository"))
        testing.expect.check(2, len(code_repository))
        testing.expect.check(repository.url, extract_text(code_repository[1]))

    return check

with frontend.signin("alice"):
    frontend.operation(
        "savesettings",
        data={ "settings": [{ "item": "email.subjectLine.updatedReview.reviewRebased",
                              "value": "Rebased Review: %(summary)s" }] })

    result = frontend.operation(
        "fetchremotebranch",
        data={
            "repository_name": "critic",
            "remote": repository.url,
            "branch": BRANCH_NAME[0],
            "upstream": "refs/heads/" + UPSTREAM_NAME[0] },
        expect={
            "head_sha1": REVIEWED_SHA1[0],
            "upstream_sha1": UPSTREAM_SHA1[0] })

    # Run a GC to make sure the objects fetched by /fetchremotebranch are
    # referenced and thus usable by the subsequent /submitreview operation.
    instance.gc("critic.git")

    commit_ids = result["commit_ids"]

    result = frontend.operation(
        "submitreview",
        data={
            "repository": "critic",
            "branch": "r/" + TEST_NAME,
            "summary": SUMMARY,
            "commit_ids": commit_ids,
            "trackedbranch": { "remote": repository.url,
                               "name": BRANCH_NAME[0] }})

    review_id = result["review_id"]
    trackedbranch_id = result["trackedbranch_id"]

    mailbox.pop(
        accept=[to("alice"),
                about("New Review: " + SUMMARY)])

    # Emulate a review rebase via /rebasetrackingreview.
    frontend.page(
        "r/%d" % review_id,
        expect={
            "tracking": check_tracking(BRANCH_NAME[0]) })
    frontend.page(
        "rebasetrackingreview",
        params={
            "id": review_id })
    result = frontend.operation(
        "fetchremotebranch",
        data={
            "repository_name": "critic",
            "remote": repository.url,
            "branch": BRANCH_NAME[1],
            "upstream": "refs/heads/" + UPSTREAM_NAME[1] },
        expect={
            "head_sha1": REVIEWED_SHA1[1],
            "upstream_sha1": UPSTREAM_SHA1[1] })

    # Run a GC to make sure the objects fetched by /fetchremotebranch are
    # referenced and thus usable by the subsequent /rebasetrackingreview
    # operation.
    instance.gc("critic.git")

    frontend.page(
        "rebasetrackingreview",
        params={
            "id": review_id,
            "newbranch": BRANCH_NAME[1],
            "upstream": UPSTREAM_NAME[1],
            "newhead": REVIEWED_SHA1[1],
            "newupstream": UPSTREAM_SHA1[1] })
    frontend.operation(
        "checkconflictsstatus",
        data={
            "review_id": review_id,
            "new_head_sha1": REVIEWED_SHA1[1],
            "new_upstream_sha1": UPSTREAM_SHA1[1] },
        expect={
            "has_changes": False,
            "has_conflicts": False })
    frontend.operation(
        "rebasereview",
        data={
            "review_id": review_id,
            "new_head_sha1": REVIEWED_SHA1[1],
            "new_upstream_sha1": UPSTREAM_SHA1[1],
            "new_trackedbranch": BRANCH_NAME[1] })
    frontend.page(
        "r/%d" % review_id,
        expect={
            "tracking": check_tracking(BRANCH_NAME[1]) })

    mailbox.pop(
        accept=[to("alice"),
                about("Rebased Review: " + SUMMARY)])

    # Disable and enable the tracking.
    frontend.operation(
        "disabletrackedbranch",
        data={
            "branch_id": trackedbranch_id })
    frontend.page(
        "r/%d" % review_id,
        expect={
            "tracking": check_tracking(BRANCH_NAME[1], disabled=True) })
    frontend.operation(
        "enabletrackedbranch",
        data={
            "branch_id": trackedbranch_id })
    frontend.page(
        "r/%d" % review_id,
        expect={
            "tracking": check_tracking(BRANCH_NAME[1]) })
