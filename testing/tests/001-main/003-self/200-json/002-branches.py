# @dependency 001-main/002-createrepository.py

stored_branches = []

def check_branches(path, branches, check):
    if not check(path, expected=list, actual=branches):
        return
    for index, branch in enumerate(branches):
        if check("%s[%d]" % (path, index),
                 expected={ "id": int,
                            "name": str,
                            "repository": 1,
                            "head": int },
                 actual=branch):
            stored_branches.append(branch)

frontend.json(
    "repositories/1/branches",
    expect={ "branches": check_branches })

for branch in stored_branches:
    frontend.json(
        "branches/%d" % branch["id"],
        expect=branch)
    frontend.json(
        "branches",
        params={ "name": branch["name"],
                 "repository": branch["repository"] },
        expect=branch)
    frontend.json(
        "repositories/%d/branches/%d" % (branch["repository"], branch["id"]),
        expect=branch)
    frontend.json(
        "repositories/%d/branches" % branch["repository"],
        params={ "name": branch["name"] },
        expect=branch)

stored_branch_heads_by_name = {}
stored_commit_sha1s_by_id = {}

def store_branches(path, branches, check):
    stored_branch_heads_by_name.update({ branch["name"]: branch["head"]
                                         for branch in branches })

def store_commits(path, commits, check):
    stored_commit_sha1s_by_id.update({ commit["id"]: commit["sha1"]
                                       for commit in commits })

frontend.json(
    "repositories/1/branches",
    params={ "include": "commits" },
    expect={ "branches": store_branches,
             "linked": { "commits": store_commits }})

for name, head_id in stored_branch_heads_by_name.items():
    if head_id not in stored_commit_sha1s_by_id:
        logger.error("linked head of branch %s (commit id=%d) not included"
                     % (name, head_id))
        continue

    expected_sha1 = repository.run(
        ["ls-remote", instance.repository_url("alice"),
         "refs/heads/" + name]).split()[0]
    actual_sha1 = stored_commit_sha1s_by_id[head_id]

    testing.expect.check(expected_sha1, actual_sha1)

def check_commits(path, commits, check):
    if not check(path, expected=list, actual=commits):
        return
    for index, commit in enumerate(commits):
        check("%s[%d]" % (path, index),
              expected=generic_commit_json,
              actual=commit)



frontend.json(
    "branches/%d/commits" % stored_branches[0]["id"],
    expect={ "commits": check_commits })

first10 = frontend.json(
    "branches/%d/commits" % stored_branches[0]["id"],
    params={ "sort": "topological",
             "fields": "id",
             "count": 10 },
    expect={ "commits": list })

frontend.json(
    "branches/%d/commits" % stored_branches[0]["id"],
    params={ "sort": "date",
             "fields": "id",
             "count": 10 },
    expect={ "commits": list })

frontend.json(
    "branches/%d/commits" % stored_branches[0]["id"],
    params={ "sort": "topological",
             "fields": "id",
             "offset": 5,
             "count": 5 },
    expect={ "commits": first10["commits"][5:] })

frontend.json(
    "branches/4711",
    expect={ "error": { "title": "No such resource",
                        "message": "Resource not found: Invalid branch id: 4711" }},
    expected_http_status=404)

frontend.json(
    "branches/master",
    expect={ "error": { "title": "Invalid API request",
                        "message": "Invalid numeric id: 'master'" }},
    expected_http_status=400)

frontend.json(
    "branches",
    params={ "name": "nosuchbranch",
             "repository": "critic" },
    expect={ "error": { "title": "No such resource",
                        "message": "Resource not found: Invalid branch name: 'nosuchbranch'" }},
    expected_http_status=404)

frontend.json(
    "branches",
    params={ "name": "nosuchbranch" },
    expect={ "error": { "title": "Invalid API request",
                        "message": "Named branch access must have repository specified." }},
    expected_http_status=400)

frontend.json(
    "branches",
    params={ "name": "master",
             "repository": "4711" },
    expect={ "error": { "title": "No such resource",
                        "message": "Resource not found: Invalid repository id: 4711" }},
    expected_http_status=404)

frontend.json(
    "branches",
    params={ "name": "master",
             "repository": "nosuchrepository" },
    expect={ "error": { "title": "No such resource",
                        "message": "Resource not found: Invalid repository name: 'nosuchrepository'" }},
    expected_http_status=404)
