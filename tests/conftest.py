import asyncio
import logging
import pytest


@pytest.fixture(scope="session")
def event_loop():
    return asyncio.new_event_loop()


def pytest_addoption(parser):
    parser.addoption(
        "--instance-type", choices=("quickstart", "docker"), default="quickstart"
    )
    parser.addoption("--keep-data", action="store_true")


logging.addLevelName(logging.DEBUG, "STDOUT")
logging.addLevelName(logging.DEBUG, "STDERR")


from .fixtures import (
    admin,
    alice,
    anonymizer,
    api,
    bob,
    carol,
    create_branch,
    create_extension,
    create_review,
    critic_repo,
    dave,
    empty_repo,
    frontend,
    git_askpass,
    instance,
    smtpd,
    test_extension,
    websocket,
    settings,
    workdir,
)


__all__ = [
    "admin",
    "alice",
    "anonymizer",
    "api",
    "bob",
    "carol",
    "create_branch",
    "create_extension",
    "create_review",
    "critic_repo",
    "dave",
    "empty_repo",
    "frontend",
    "git_askpass",
    "instance",
    "smtpd",
    "test_extension",
    "websocket",
    "settings",
    "workdir",
]
