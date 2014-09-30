# @dependency 001-main/001-empty/003-criticctl/002-adduser-deluser.py
# @dependency 001-main/001-empty/004-mixed/003-oauth.py
# @dependency 001-main/001-empty/004-mixed/004-password.py
# @dependency 001-main/003-self/028-gitemails.py

args = []
if not testing.has_flag(instance.install_commit,
                        "reliable-git-emails"):
    args.append("--unreliable-git-emails")
if not testing.has_flag(instance.install_commit,
                        "reliable-admin-newswriter"):
    args.append("--unreliable-admin-newswriter")
instance.unittest("api.user", ["basic"], args)

settings_per_user = testing.utils.settings(
    "alice", { "commit.diff.visualTabs": True })
settings_per_repository = testing.utils.settings(
    "alice", { "commit.expandAllFiles": True },
    repository="critic")

with settings_per_user, settings_per_repository:
    instance.unittest("api.user", ["preferences"])
