# @dependency 001-main/002-createrepository.py

with repository.workcopy() as work:
    review = Review(work, "alice", "200-json/008-batches")
    review.addFile(first="200-json/008-batches/first.txt",
                   second="200-json/008-batches/second.txt",
                   third="200-json/008-batches/third.txt")
    review.commit("Reference commit",
                  reference=True,
                  first=["First",
                         "=====",
                         "Initial line"],
                  second=["Second",
                          "======",
                          "Initial line"],
                  third=["Third",
                         "=====",
                         "Initial line"])
    review.commit("First commit",
                  first=["First",
                         "=====",
                         "Initial line",
                         "Added line"])
    review.commit("Second commit",
                  second=["Second",
                          "======",
                          "Initial line",
                          "Added line"])
    review.commit("Third commit",
                  third=["Third",
                         "=====",
                         "Initial line",
                         "Added line"])
    review.addFilter("bob", "reviewer", "200-json/008-batches/")
    review.addFilter("dave", "reviewer", "200-json/008-batches/")
    review.submit()

    changesets = {
        "first": fetch_changeset({
            "from": review.sha1s[0],
            "to": review.sha1s[1],
        }),
        "second": fetch_changeset({
            "from": review.sha1s[1],
            "to": review.sha1s[2],
        }),
        "third": fetch_changeset({
            "from": review.sha1s[2],
            "to": review.sha1s[3],
        }),
        "all": fetch_changeset({
            "from": review.sha1s[0],
            "to": review.sha1s[3],
        }),
    }

    issues = {
        "alice": [],
        "bob": [],
        "dave": []
    }

    changes = {}

    def fetch_changes(key):
        changes[key] = frontend.json(
            ("reviews/%d/changesets/%d/reviewablefilechanges"
             % (review.id, changesets[key]["id"])),
            expect={
                "reviewablefilechanges": [{
                    "id": int,
                    "review": review.id,
                    "changeset": changesets[key]["id"],
                    "file": review.getFileId(key),
                    "deleted_lines": int,
                    "inserted_lines": int,
                    "is_reviewed": False,
                    "reviewed_by": None,
                    "assigned_reviewers": [instance.userid("bob"),
                                           instance.userid("dave")],
                    "draft_changes": None,
                }],
            })["reviewablefilechanges"]

    fetch_changes("first")
    fetch_changes("second")
    fetch_changes("third")

    with frontend.signin("alice"):
        frontend.json(
            "reviews/%d/batches" % review.id,
            params={
                "unpublished": "yes",
            },
            expect=batch_json(review.id, "alice", "draft"))

        issues["alice"].append(
            frontend.json(
                "reviews/%d/issues" % review.id,
                post={
                    "text": "Alice's issue #1",
                    "location": {
                        "type": "file-version",
                        "changeset": changesets["first"]["id"],
                        "side": "new",
                        "file": review.getFilename("first"),
                        "first_line": 1,
                        "last_line": 4,
                    }
                })["id"])

        frontend.json(
            "reviews/%d/batches" % review.id,
            params={
                "unpublished": "yes",
            },
            expect=batch_json(review.id, "alice", "draft",
                              created_comments=[issues["alice"][0]]))

        issues["alice"].append(
            frontend.json(
                "reviews/%d/issues" % review.id,
                post={
                    "text": "Alice's issue #2",
                    "location": {
                        "type": "file-version",
                        "changeset": changesets["second"]["id"],
                        "side": "new",
                        "file": review.getFilename("second"),
                        "first_line": 1,
                        "last_line": 2,
                    }
                })["id"])

        frontend.json(
            "reviews/%d/batches" % review.id,
            params={
                "unpublished": "yes",
            },
            expect=batch_json(review.id, "alice", "draft",
                              created_comments=[issues["alice"][0],
                                                issues["alice"][1]]))

        frontend.json(
            "reviews/%d/batches" % review.id,
            post={},
            expect=batch_json(review.id, "alice", "published",
                              created_comments=[issues["alice"][0],
                                                issues["alice"][1]]))

        frontend.json(
            "reviews/%d/batches" % review.id,
            params={
                "unpublished": "yes",
            },
            expect=batch_json(review.id, "alice", "draft"))

    with frontend.signin("bob"):
        frontend.json(
            "reviews/%d/batches" % review.id,
            params={
                "unpublished": "yes",
            },
            expect=batch_json(review.id, "bob", "draft"))

        issues["bob"].append(
            frontend.json(
                "reviews/%d/issues" % review.id,
                post={
                    "text": "Bob's issue #1",
                    "location": {
                        "type": "file-version",
                        "changeset": changesets["second"]["id"],
                        "side": "new",
                        "file": review.getFilename("second"),
                        "first_line": 3,
                        "last_line": 4,
                    }
                })["id"])

        frontend.json(
            "comments/%d" % issues["alice"][0],
            put={
                "draft_changes": {
                    "new_state": "resolved",
                },
            },
            expect={
                "id": issues["alice"][0],
                "state": "open",
                "draft_changes": draft_changes_json(
                    "bob", new_state="resolved"),
                "*": "*",
            })

        frontend.json(
            ("reviews/%d/changesets/%d/reviewablefilechanges"
             % (review.id, changesets["second"]["id"])),
            put={
                "draft_changes": {
                    "new_is_reviewed": True,
                }
            },
            expect={
                "reviewablefilechanges": [{
                    "id": int,
                    "review": review.id,
                    "changeset": changesets["second"]["id"],
                    "file": review.getFileId("second"),
                    "deleted_lines": int,
                    "inserted_lines": int,
                    "is_reviewed": False,
                    "reviewed_by": None,
                    "assigned_reviewers": [instance.userid("bob"),
                                           instance.userid("dave")],
                    "draft_changes": {
                        "author": instance.userid("bob"),
                        "new_is_reviewed": True,
                        "new_reviewed_by": instance.userid("bob"),
                    },
                }],
            })

        frontend.json(
            "reviews/%d/batches" % review.id,
            params={
                "unpublished": "yes",
            },
            expect=batch_json(review.id, "bob", "draft",
                              created_comments=[issues["bob"][0]],
                              resolved_issues=[issues["alice"][0]],
                              reviewed_changes=[changes["second"][0]["id"]]))

    with frontend.signin("dave"):
        frontend.json(
            "reviews/%d/batches" % review.id,
            params={
                "unpublished": "yes",
            },
            expect=batch_json(review.id, "dave", "draft"))

        issues["dave"].append(
            frontend.json(
                "reviews/%d/issues" % review.id,
                post={
                    "text": "Dave's issue #1",
                    "location": {
                        "type": "file-version",
                        "changeset": changesets["all"]["id"],
                        "side": "new",
                        "file": review.getFilename("third"),
                        "first_line": 1,
                        "last_line": 4,
                    }
                })["id"])

        frontend.json(
            "comments/%d" % issues["alice"][0],
            put={
                "draft_changes": {
                    "new_state": "resolved",
                },
            },
            expect={
                "id": issues["alice"][0],
                "state": "open",
                "draft_changes": draft_changes_json(
                    "dave", new_state="resolved"),
                "*": "*",
            })

        frontend.json(
            "comments/%d" % issues["alice"][1],
            put={
                "draft_changes": {
                    "new_state": "resolved",
                },
            },
            expect={
                "id": issues["alice"][1],
                "state": "open",
                "draft_changes": draft_changes_json(
                    "dave", new_state="resolved"),
                "*": "*",
            })

        frontend.json(
            "reviewablefilechanges/%d,%d" % (changes["second"][0]["id"],
                                             changes["third"][0]["id"]),
            put={
                "draft_changes": {
                    "new_is_reviewed": True,
                }
            },
            expect={
                "reviewablefilechanges": [{
                    "id": int,
                    "review": review.id,
                    "changeset": changesets["second"]["id"],
                    "file": review.getFileId("second"),
                    "deleted_lines": int,
                    "inserted_lines": int,
                    "is_reviewed": False,
                    "reviewed_by": None,
                    "assigned_reviewers": [instance.userid("bob"),
                                           instance.userid("dave")],
                    "draft_changes": {
                        "author": instance.userid("dave"),
                        "new_is_reviewed": True,
                        "new_reviewed_by": instance.userid("dave"),
                    },
                }, {
                    "id": int,
                    "review": review.id,
                    "changeset": changesets["third"]["id"],
                    "file": review.getFileId("third"),
                    "deleted_lines": int,
                    "inserted_lines": int,
                    "is_reviewed": False,
                    "reviewed_by": None,
                    "assigned_reviewers": [instance.userid("bob"),
                                           instance.userid("dave")],
                    "draft_changes": {
                        "author": instance.userid("dave"),
                        "new_is_reviewed": True,
                        "new_reviewed_by": instance.userid("dave"),
                    },
                }],
            })

        frontend.json(
            "reviews/%d/batches" % review.id,
            params={
                "unpublished": "yes",
            },
            expect=batch_json(review.id, "dave", "draft",
                              created_comments=[issues["dave"][0]],
                              resolved_issues=[issues["alice"][0],
                                               issues["alice"][1]],
                              reviewed_changes=[changes["second"][0]["id"],
                                                changes["third"][0]["id"]]))

    with frontend.signin("bob"):
        frontend.json(
            "reviews/%d/batches" % review.id,
            params={
                "unpublished": "yes",
            },
            expect=batch_json(review.id, "bob", "draft",
                              created_comments=[issues["bob"][0]],
                              resolved_issues=[issues["alice"][0]],
                              reviewed_changes=[changes["second"][0]["id"]]))

        frontend.json(
            "reviews/%d/batches" % review.id,
            post={
                "comment": "This looks good!",
            },
            expect=batch_json(review.id, "bob", "published",
                              comment=int,
                              created_comments=[issues["bob"][0]],
                              resolved_issues=[issues["alice"][0]],
                              reviewed_changes=[changes["second"][0]["id"]]))

        frontend.json(
            "reviews/%d/batches" % review.id,
            params={
                "unpublished": "yes",
            },
            expect=batch_json(review.id, "bob", "draft"))

    with frontend.signin("dave"):
        frontend.json(
            "reviews/%d/batches" % review.id,
            params={
                "unpublished": "yes",
            },
            expect=batch_json(review.id, "dave", "draft",
                              created_comments=[issues["dave"][0]],
                              resolved_issues=[issues["alice"][1]],
                              reviewed_changes=[changes["third"][0]["id"]]))

# eof
