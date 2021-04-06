import logging
from typing import Optional

logger = logging.getLogger(__name__)

from ..repository import ensure as ensure_repository, ExecuteError
from ..session import session
from ..user import ensure as ensure_user
from ..utils import git_askpass
from ..websocket import connect as connect_websocket

BRANCH_NAME = "r/jl/split-git-hook"

COMMITS = [
    "cf056e5756099d0fc16d85432d4e4b05f13f1254",
    "295ebf6f2ebdc256940dac7590c27352efac9d94",
    "f274b35558983a28808910583271b40b05c1144d",
    "ddf3206ec8c1a6b57cff1f1b4faec34f71517d93",
    "b94431e7662a401fabe66da314743fcc6cd04f49",
    "bae620a9b969348cee0ec0f182d31df13101c9c0",
    "99d38989dd7623dd56e78f4ceb7e52e7c6c5946e",
    "14a90cd99fdc053010330431f19ba9794b7d7248",
    "d6ce6cbbb2fc5ba71d9a5cd20275ec4799ff4085",
    "1c57153e8cf73ea30636b7db0bd7fca57c78dda6",
    "2eb4e0a96dcf4eb139ffa3b31cc9ce7b949cdbd1",
    "ded93054a4f00b1086005d915e943bf370df3982",
    "1b872ba35bf377b5679e71f86c7b3a0b78508682",
    "cb9312d75c4adcdc73568499692ce9df0b930166",
    "875a3b71215aadb7c7e8576c42f93427ae384777",
    "36fffd501215cf36e8b30f7bd390803890a26711",
    "a729bbc3f2ee917e82759b279c9500f64a17f7a2",
    "45a829dcf97b5f0e1dcf0aa7f668451ba65fa4ef",
    "c3aa391bed025599f1c9df1b6c262ac413ea76a3",
    "fe9b4c2ca07053d68454c36cb3e13c084a8c44c4",
    "debeb8a964fb052870922aaf1f540b7960e51ce9",
    "ea5a9e75b6180e2201ecb0b18ed68b6a7880fee2",
    "50bb8349ae6988d9771a3603467c4081f2553cf3",
    "3924f0ed7b57af58ff951c693d49bf2474a9941c",
    "f4ab0495b4fd1dc40494f2348c521d23374cb247",
    "d9c495058037a5ad637d44fd3020e1bb6cdc4236",
]


async def main() -> None:
    alice = await ensure_user("alice")
    bob = await ensure_user("bob")
    critic_git = await ensure_repository("critic")

    async with critic_git.workcopy(bare=True) as workcopy:
        await workcopy.run(
            "git", "config", "remote.upstream.fetch", "refs/*:refs/remotes/upstream/*"
        )
        await workcopy.run("git", "fetch", "upstream")
        await workcopy.run("git", "config", "credential.username", alice.name)

        async def push(commit: str, force: Optional[bool] = False) -> str:
            push_args = ["--force"] if force else []
            with git_askpass():
                stdout = await workcopy.run(
                    "git",
                    "push",
                    *push_args,
                    "origin",
                    f"{commit}:refs/heads/{BRANCH_NAME}",
                )
                for line in stdout.splitlines():
                    logger.info(line)
            return commit

        async with connect_websocket() as websocket:
            previous = await push(COMMITS.pop(0))

            async with session("alice") as backend:
                review = await backend.get(
                    "reviews", repository=critic_git.full_name, branch=BRANCH_NAME
                )
                review_id = review["id"]

                await backend.post(
                    f"reviewfilters",
                    {"subject": bob.name, "type": "reviewer", "path": ""},
                    review=review_id,
                )

                await backend.put(
                    f"reviews/{review_id}",
                    {
                        "summary": "Split pre-receive Git hook into pre-receive + post-receive",
                        "state": "open",
                        "integration": {"target_branch": "master"},
                    },
                )

            for commit in COMMITS:
                try:
                    await workcopy.run(
                        "git", "merge-base", "--is-ancestor", previous, commit
                    )
                except ExecuteError:
                    force = True
                else:
                    force = False

                branchupdate = await websocket.expect(
                    "reviewevents", review_id=review_id, event_type="branchupdate"
                )

                await push(commit, force=force)
                await branchupdate
