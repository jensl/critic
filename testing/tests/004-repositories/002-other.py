# @user alice

# Add another repository. This time using criticctl and without a tracking
# branch, but we'll actually push the same branch (IOW our current branch of
# critic.git) to it, simply because we don't really have another available
# with anything useful in it.
instance.criticctl(["addrepository", "--name", "other", "--path", "other"])

repository.run(
    [
        "push",
        instance.repository_url("alice", repository="other"),
        "HEAD:refs/heads/master",
    ]
)

instance.register_repository(frontend.json("repositories", params={"name": "other"}))
