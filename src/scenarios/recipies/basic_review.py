from ..repository import ensure as ensure_repository
from ..user import ensure as ensure_user
from ..utils import git_askpass

BRANCH_NAME = "r/jl/split-git-hook"


async def main() -> None:
    alice = await ensure_user("alice")
    critic_git = await ensure_repository(
        "critic", "https://critic-review.org/critic.git"
    )

    async with critic_git.workcopy() as workcopy:
        await workcopy.run("git", "fetch", "upstream")
        await workcopy.run("git", "config", "credential.username", alice.name)

        with git_askpass():
            await workcopy.run(
                "git",
                "push",
                "origin",
                f"upstream/{BRANCH_NAME}:refs/heads/{BRANCH_NAME}",
            )
