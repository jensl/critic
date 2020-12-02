import asyncio
import io
import logging
import os
import shutil
import tempfile
import time
import venv
import zipfile
from pathlib import Path
from typing import Optional, cast

logger = logging.getLogger(__name__)

from critic import api
from critic.background import extensiontasks


def unzip(target_dir: str, data: bytes) -> None:
    with zipfile.ZipFile(io.BytesIO(data)) as file:
        file.extractall(os.path.join(target_dir, "src"))


def create_venv(target_dir: str) -> None:
    builder = venv.EnvBuilder(with_pip=True)
    builder.create(target_dir)


async def prepare_extension(
    critic_wheel: Optional[Path],
    source_dir: Optional[Path],
    target_dir: Path,
    extension_name: str,
    version_id: int,
    manifest: api.extensionversion.ExtensionVersion.Manifest,
) -> None:
    logger.debug("%s: preparing...", target_dir)

    loop = asyncio.get_running_loop()

    assert (critic_wheel is None) != (source_dir is None)

    prepared_path = target_dir / ".prepared"

    def mtime(path: Path) -> float:
        return path.stat().st_mtime

    if critic_wheel:
        critic_wheel_mtime = mtime(critic_wheel)

        if target_dir.is_dir():
            if prepared_path.exists():
                if mtime(prepared_path) < critic_wheel_mtime:
                    logger.debug(
                        "%s: existing version dir has out-of-date Critic version",
                        target_dir,
                    )
                else:
                    logger.debug("%s: using pre-existing version dir", target_dir)
                    return
            else:
                logger.debug(
                    "%s: deleting unfinished pre-existing version dir", target_dir
                )
            await loop.run_in_executor(None, shutil.rmtree, target_dir)

        install_critic_args = [str(critic_wheel)]
    else:
        if prepared_path.exists():
            logger.debug("%s: using pre-existing version dir", target_dir)
            return

        install_critic_args = ["-e", str(source_dir)]

    pip = os.path.join(target_dir, "bin", "pip")

    async def fetch_and_extract(temporary_dir: str) -> None:
        logger.debug("%s: fetching extension archive...", target_dir)
        data = (await extensiontasks.archive_version(version_id)).data
        logger.debug("%s: extracting extension archive...", target_dir)
        await loop.run_in_executor(None, unzip, temporary_dir, data)

    async def prepare_venv() -> None:
        logger.debug("%s: creating virtual environment...", target_dir)
        await loop.run_in_executor(None, create_venv, target_dir)
        process = await asyncio.create_subprocess_exec(
            pip,
            "install",
            "--upgrade",
            "pip",
            "wheel",
            stdout=asyncio.subprocess.DEVNULL,
        )
        await process.wait()
        logger.debug("%s: installing Critic...", target_dir)
        process = await asyncio.create_subprocess_exec(
            pip,
            "install",
            *install_critic_args,
            stdout=asyncio.subprocess.DEVNULL,
        )
        await process.wait()

    with tempfile.TemporaryDirectory() as temporary_dir:
        completed, pending = await asyncio.wait(
            [
                asyncio.create_task(
                    fetch_and_extract(temporary_dir), name="fetch and extract extension"
                ),
                asyncio.create_task(prepare_venv(), name="prepare virtual environment"),
            ]
        )
        assert not pending

        failed = False
        for task in completed:
            try:
                await task
            except Exception as error:
                logger.error(
                    "Task failed: %s: %s",
                    cast(asyncio.Task[None], task).get_name(),
                    error,
                )
                failed = True

        if failed:
            raise Exception("Failed to prepare extension")

        package = manifest.package

        assert package.package_type == "python"

        with open(os.path.join(temporary_dir, "setup.py"), "w") as setup_py:
            print("from setuptools import setup", file=setup_py)
            print("setup()", file=setup_py)

        with open(os.path.join(temporary_dir, "setup.cfg"), "w") as setup_cfg:
            print("[metadata]", file=setup_cfg)
            print(f"name={extension_name}", file=setup_cfg)

            print("[options]", file=setup_cfg)
            print("package_dir=\n    =src", file=setup_cfg)
            print("packages=find:", file=setup_cfg)

            if package.dependencies:
                print("install_requires=", file=setup_cfg)
                for dependency in package.dependencies:
                    print(f"    {dependency}", file=setup_cfg)

            print("[options.packages.find]", file=setup_cfg)
            print("where=src", file=setup_cfg)

            # if manifest.package.entrypoints:
            #     print("[options.entry_points]", file=setup_cfg)
            #     print("console_scripts=", file=setup_cfg)
            #     for name, target in manifest.package.entrypoints.items():
            #         print(f"    {name}={target}", file=setup_cfg)

        logger.debug("%s: installing extension...", target_dir)
        process = await asyncio.create_subprocess_exec(
            pip, "install", temporary_dir, stdout=asyncio.subprocess.DEVNULL
        )
        await process.wait()

    with open(prepared_path, "w") as file:
        print(time.ctime(), file=file)

    if critic_wheel:
        critic_wheel_mtime = mtime(critic_wheel)

        os.utime(prepared_path, (critic_wheel_mtime, critic_wheel_mtime))

    logger.debug("%s: finished", target_dir)
