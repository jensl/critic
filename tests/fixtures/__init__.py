import asyncio
import pytest
from typing import Any, Dict, Iterable, List, Optional, Protocol, Sequence, Set

from ..utilities import Anonymizer, Snapshot, Frozen, generate_name


class Marker(Protocol):
    @property
    def args(self) -> Sequence[Any]:
        ...


class Node(Protocol):
    @property
    def name(self) -> str:
        ...

    def get_closest_marker(self, name: str, /) -> Optional[Marker]:
        ...


class Config(Protocol):
    def getoption(self, name: str, /) -> Optional[str]:
        ...


class Request(Protocol):
    @property
    def node(self) -> Node:
        ...


@pytest.fixture(scope="session")
def event_loop():
    """A session-scoped event loop."""
    return asyncio.new_event_loop()


@pytest.fixture
def anonymizer(snapshot) -> Anonymizer:
    def resource_filters(resource_name: str, *suffixes: str) -> Sequence[str]:
        if suffixes and suffixes[0]:
            suffixes = tuple(f"[*].{suffix}" for suffix in suffixes)
        elif suffixes:
            suffixes = ("[*]",)
        else:
            suffixes = ("",)
        return [
            f"$.response.data.{selector}{suffix}"
            for suffix in suffixes
            for selector in (resource_name, f"linked.{resource_name}")
        ]

    def default_filters(resource_name: str) -> Sequence[str]:
        return [
            *resource_filters(resource_name, "id"),
            f'$.publish[message.resource_name="{resource_name}"].message.object_id',
            f"$.request.path:(?<=api/v1/{resource_name}/)\d+",
            f"$.publish[*].channel[*]:(?<={resource_name}/)(\d+)",
        ]

    def message_filters(resource_name: str, *suffixes: str) -> Sequence[str]:
        return [
            f'$.publish[message.resource_name="{resource_name}"].{suffix}'
            for suffix in suffixes
        ]

    anonymizer = Anonymizer(
        snapshot,
        AccessTokenId=[*default_filters("accesstokens")],
        BatchId=[*default_filters("batches")],
        BranchId=[
            *default_filters("branches"),
            *resource_filters("branchupdates", "branch"),
            *resource_filters("reviews", "branch"),
            "$.response.data.branches[*].base_branch",
            "$.publish[*].message.branch_id",
        ],
        BranchUpdateId=[
            *default_filters("branchupdates"),
            *resource_filters("branches", "updates[*]"),
        ],
        ChangesetId=[
            *default_filters("changesets"),
            *resource_filters("filechanges", "changeset"),
            *resource_filters("filediffs", "changeset"),
            *resource_filters("reviewablefilechanges", "changeset"),
            *resource_filters("reviews", "changesets[*]"),
        ],
        CommentId=[
            *default_filters("comments"),
            *resource_filters(
                "batches",
                "comment",
                "created_comments[*]",
                "reopened_issues[*]",
                "resolved_issues[*]",
            ),
            *resource_filters("replies", "comment"),
            *resource_filters("reviews", "issues[*]", "notes[*]"),
        ],
        CommitId=[
            *default_filters("commits"),
            *resource_filters(
                "changesets", "from_commit", "to_commit", "contributing_commits[*]"
            ),
            *resource_filters("commits", "parents[*]"),
            *resource_filters(
                "branchupdates",
                "from_head",
                "to_head",
                "associated[*]",
                "disassociated[*]",
            ),
            *resource_filters(
                "reviews", "partitions[*].commits[*]", "progress_per_commit[*].commit"
            ),
            "$.response.data.branches[*].head",
        ],
        CommitSHA1=[*resource_filters("commits", "sha1")],
        ExtensionId=[
            *default_filters("extensions"),
            *resource_filters("extensioninstallations", "extension"),
            *resource_filters("extensionversions", "extension"),
        ],
        ExtensionInstallationId=[*default_filters("extensioninstallations")],
        ExtensionVersionId=[
            *default_filters("extensionversions"),
            *resource_filters("extensioninstallations", "version"),
            *resource_filters("extensions", "versions[*]"),
        ],
        ExtensionVersionSHA11=[*resource_filters("extensionversions", "sha1")],
        FileId=[
            *default_filters("files"),
            *resource_filters("changesets", "files[*]"),
            *resource_filters("filechanges", "file"),
            *resource_filters("filediffs", "file"),
            *resource_filters("reviewablefilechanges", "file"),
        ],
        FileSHA1=[*resource_filters("filechanges", "new_sha1", "old_sha1"),],
        ReplyId=[
            *default_filters("replies"),
            *resource_filters("batches", "written_replies[*]"),
            *resource_filters("comments", "draft_changes.reply", "replies[*]"),
        ],
        RepositoryFilterId=[*default_filters("repositoryfilters")],
        RepositoryId=[
            *default_filters("repositories"),
            *resource_filters("branches", "repository"),
            *resource_filters("changesets", "repository"),
            *resource_filters("repositoryfilters", "repository"),
            *resource_filters("reviews", "repository"),
            *resource_filters("reviewscopefilters", "repository"),
            "$.publish[*].message.repository_id",
        ],
        RepositoryName=[*resource_filters("repositories", "name")],
        RepositoryPath=[
            *resource_filters("repositories", "path"),
            f'$.publish[message.resource_name="repositories"].message.path',
        ],
        ReviewId=[
            *default_filters("reviews"),
            *resource_filters("batches", "review"),
            *resource_filters("changesets", "review_state.review"),
            *resource_filters("comments", "review"),
            *resource_filters("reviewablefilechanges", "review"),
            *resource_filters("reviewfilters", "review"),
            "$.publish[*].message.review_id",
        ],
        ReviewEventId=[*default_filters("reviewevents"),],
        ReviewFilterId=[
            *default_filters("reviewfilters"),
            *resource_filters("reviews", "filters[*]"),
        ],
        ReviewScopeId=[
            *default_filters("reviewscopes"),
            *resource_filters("repositoryfilters", "scopes[*]"),
            *resource_filters("reviewscopefilters", "scope"),
            *resource_filters("reviewablefilechanges", "scope"),
        ],
        ReviewScopeFilterId=[*default_filters("reviewscopefilters"),],
        ReviewTagId=[
            *default_filters("reviewtags"),
            *resource_filters("reviews", "tags[*]"),
        ],
        ReviewableFileChangeId=[
            *default_filters("reviewablefilechanges"),
            *resource_filters(
                "batches", "reviewed_changes[*]", "unreviewed_changes[*]"
            ),
            *resource_filters("changesets", "review_state.reviewablefilechanges[*]"),
        ],
        Timestamp=[
            *resource_filters("branchupdates", "timestamp"),
            *resource_filters("batches", "timestamp"),
            *resource_filters("comments", "timestamp"),
            *resource_filters("commits", "author.timestamp", "committer.timestamp"),
            *resource_filters("replies", "timestamp"),
            *resource_filters("reviews", "last_changed"),
        ],
        TreeSHA1=[*resource_filters("commits", "tree")],
        UserId=[
            *default_filters("users"),
            *resource_filters("accesstokens", "user"),
            *resource_filters("batches", "author"),
            *resource_filters("branchupdates", "updater"),
            *resource_filters("comments", "author", "draft_changes.author"),
            *resource_filters("replies", "author"),
            *resource_filters("repositoryfilters", "subject", "delegates[*]"),
            *resource_filters(
                "reviewablefilechanges",
                "assigned_reviewers[*]",
                "reviewed_by[*]",
                "draft_changes.author",
            ),
            *resource_filters(
                "reviews",
                "owners[*]",
                "active_reviewers[*]",
                "assigned_reviewers[*]",
                "watchers[*]",
            ),
            *resource_filters("reviewfilters", "subject", "creator"),
            *resource_filters("sessions", "user"),
            "$.publish[*].message.user_id",
        ],
    )

    def define_commit_id(commit: dict) -> dict:
        if anonymizer.lookup(CommitId=commit["id"]) is None:
            label = anonymizer.lookup(CommitSHA1=commit["sha1"])
            if isinstance(label, str):
                anonymizer.define(CommitId={label: commit["id"]})
        return commit

    def maybe_set(value: Optional[Iterable[Any]]) -> Optional[Set[Any]]:
        if value is None:
            return None
        return set(value)

    def frozen_set(items: Iterable[Dict[str, Any]]) -> Set[Frozen]:
        return {Frozen(item) for item in items}

    def convert_linked(
        value: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Set[Frozen]]:
        return {name: {Frozen(item) for item in items} for name, items in value.items()}

    return (
        anonymizer.define(Timestamp={"": None})
        .convert(resource_filters("branchupdates", "associated"), set)
        .convert(resource_filters("branchupdates", "disassociated"), set)
        .convert(resource_filters("changesets", "files"), maybe_set)
        .convert(resource_filters("commits", ""), define_commit_id)
        .convert("$.response.data.filechanges", frozen_set)
        .convert("$.response.data.filediffs", frozen_set)
        .convert("$.response.data.linked", convert_linked)
    )


from .repository import git_askpass, empty_repo, critic_repo
from .workdir import workdir
from .instance import instance
from .frontend import frontend
from .api import api
from .websocket import websocket
from .users import admin, alice, bob, carol, dave
from .review import create_review
from .branch import create_branch
from .extension import create_extension, test_extension
from .smtpd import smtpd
from .settings import settings
