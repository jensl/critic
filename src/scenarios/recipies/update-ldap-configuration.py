import logging
from typing import Optional

logger = logging.getLogger(__name__)

from ..repository import ensure as ensure_repository, ExecuteError
from ..session import session
from ..user import ensure as ensure_user
from ..utils import git_askpass
from ..websocket import Object, connect as connect_websocket

BRANCH_NAME = "r/jl/ldap/fields-from-user"

COMMITS = [
    "793618dfb430e5abc80b8bf0af193e1c611a02f3",
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
            is_ready = await websocket.expect("reviews", updates=Object(is_ready=True))

            previous = await push(COMMITS.pop(0))

            await is_ready

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
                        "summary": "Update LDAP portion of configuration/auth.py template [stable/1]",
                        "state": "open",
                        "integration": {"target_branch": "stable/1"},
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
