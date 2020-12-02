import logging
from collections import namedtuple
from typing import List, Optional

logger = logging.getLogger(__name__)

from critic import api
from critic import gitaccess
from critic.gitaccess import SHA1, as_sha1

KEEPALIVE_REF_CHAIN = "refs/internal/keepalive-chain"
KEEPALIVE_REF_PREFIX = "refs/keepalive/"

Ref = namedtuple("Ref", ["index", "sha1", "timestamp"])


async def pack_keepalive_refs(repository: gitaccess.GitRepository) -> bool:
    """
    Pack the repository's keepalive refs into a single chain
    """

    def splitRefs(output: bytes) -> List[Ref]:
        return [
            Ref(int(timestamp.split()[0]), sha1, timestamp)
            for sha1, _, timestamp in (
                line.partition(":") for line in output.decode().splitlines()
            )
            # Skip the root commit, which has summary "Root".
            if len(sha1) == 40
        ]

    loose_keepalive_refs = splitRefs(
        await repository.run(
            "for-each-ref",
            "--sort=committerdate",
            "--format=%(objectname):%(committerdate:raw)",
            KEEPALIVE_REF_PREFIX,
        )
    )

    if not loose_keepalive_refs:
        # No loose refs => no need to (re)pack.
        return False

    try:
        old_value = await repository.revparse(KEEPALIVE_REF_CHAIN)
    except gitaccess.GitReferenceError:
        old_value = as_sha1("0" * 40)
        packed_keepalive_refs = []
    else:
        packed_keepalive_refs = splitRefs(
            await repository.run(
                "log", "--first-parent", "--date=raw", "--format=%s:%cd", old_value
            )
        )

    keepalive_refs = sorted(packed_keepalive_refs + loose_keepalive_refs)

    repository.set_user_details("Critic System", api.critic.getSystemEmail())

    new_value: Optional[SHA1] = None

    async def createRef(target: Optional[Ref] = None) -> None:
        nonlocal new_value
        parents = []
        if new_value:
            parents.append(new_value)
        if target:
            parents.append(target.sha1)
            message = target.sha1
        else:
            message = "Root"
        with repository.with_environ(
            GIT_AUTHOR_DATE=ref.timestamp, GIT_COMMITTER_DATE=ref.timestamp
        ):
            new_value = await repository.committree(
                gitaccess.EMPTY_TREE_SHA1, parents, message,
            )

    # Note: we don't keep the generated commits alive by updating refs while
    # doing this.  Since commit-tree itself produces unreferenced objects,
    # it seems unlikely it will ever run an automatic GC, and if someone
    # else triggers a GC while we're working, and it prunes our objects,
    # then we'll fail, which is no big deal (we'd just leave the existing
    # keepalive refs unmodified.)
    #
    # Also note: in most cases, the repacked keepalive chain will end up
    # reusing the commit objects from the existing keepalive chain, since
    # all meta-data in the generated commits come from the commits that we
    # keep alive, and the order stable.

    try:
        processed = set()

        await createRef()

        for ref in keepalive_refs:
            if ref.sha1 in processed:
                continue
            processed.add(ref.sha1)

            await createRef(ref)

        assert new_value

        await repository.updateref(
            KEEPALIVE_REF_CHAIN, new_value=new_value, old_value=old_value
        )
    except gitaccess.GitError:
        # No big deal if this fails here; this is just a maintenance
        # operation.  We'll try again another day.
        logger.exception("Failed to pack keepalive refs!")
        return False

    for ref in loose_keepalive_refs:
        try:
            await repository.updateref(
                KEEPALIVE_REF_PREFIX + ref.sha1, old_value=ref.sha1, delete=True
            )
        except gitaccess.GitError:
            # Ignore failures to delete loose keepalive refs.
            logger.exception("%s: failed to delete loose keepalive ref!", ref.sha1)

    return True
