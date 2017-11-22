from __future__ import annotations

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

from . import Request

from critic import api
from critic import gitaccess
from critic.gitaccess import SHA1


class ScanExternalResult:
    def __init__(self) -> None:
        self.head_sha1: Optional[SHA1] = None
        self.versions: Dict[str, str] = {}


class ScanExternal(Request[ScanExternalResult]):
    def __init__(self, uri: str):
        self.uri = uri

    async def dispatch(self, critic: api.critic.Critic) -> ScanExternalResult:
        gitrepository = gitaccess.GitRepository.direct()
        scan_result = ScanExternalResult()
        try:
            remote_refs = await gitrepository.lsremote(
                self.uri, "HEAD", "refs/heads/version/*"
            )
        except gitaccess.GitError as error:
            logger.exception("Error scanning external extension repository")
            raise
        for refname, value in remote_refs.refs.items():
            if refname == "HEAD":
                scan_result.head_sha1 = value
            elif refname.startswith("refs/heads/version/"):
                branch_name = refname[len("refs/heads/") :]
                scan_result.versions[branch_name] = value
        return scan_result


async def scan_external(critic: api.critic.Critic, uri: str) -> ScanExternalResult:
    return await ScanExternal(uri).issue()
