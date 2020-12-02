# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2013 Jens Lindström, Opera Software ASA
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License.  You may obtain a copy of
# the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
# License for the specific language governing permissions and limitations under
# the License.

import argparse
import base64
import distutils.spawn
import functools
import hashlib
import io
import json
import multiprocessing
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
from tarfile import TarFile
from typing import Any, Callable, Literal, Mapping, Tuple
import zipfile
from zipfile import ZipFile

UI_DIR = Path(__file__).resolve().parent
DATA_DIR = UI_DIR.parent / "src" / "critic" / "data"

EXTENSIONS_TO_COMPRESS = {"css", "eot", "html", "js", "map", "svg", "ttf"}
EXTENSIONS_TO_STORE = {"br", "gz", "png", "woff", "woff2"}

COMPRESS_GLOB = "js/*.js"


def executable_argument(name: str) -> Mapping[str, Any]:
    path = distutils.spawn.find_executable(name)
    if path is None:
        return {"required": True}
    return {"default": path}


Algorithm = Literal["gzip", "brotli"]


def compress(algorithm: Algorithm, path: Path) -> Tuple[Algorithm, Path, float]:
    with open(path, "rb") as uncompressed_file:
        uncompressed_data = uncompressed_file.read()
        uncompressed_size = len(uncompressed_data)

    if algorithm == "gzip":
        import gzip

        compressed_path = path.with_name(path.name + ".gz")
        with gzip.open(compressed_path, "wb") as gzip_file:
            gzip_file.write(uncompressed_data)
    elif algorithm == "brotli":
        import brotli

        compressed_path = path.with_name(path.name + ".br")
        with open(compressed_path, "wb") as brotli_file:
            brotli_file.write(brotli.compress(uncompressed_data))
    else:
        raise Exception("invalid algorithm")

    compressed_size = compressed_path.stat().st_size
    return (algorithm, compressed_path, compressed_size / uncompressed_size)


def main():
    compression_choices = ["gzip"]

    try:
        import brotli as _
    except ImportError:
        pass
    else:
        compression_choices.append("brotli")

    parser = argparse.ArgumentParser(
        "Critic UI builder", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--development",
        action="store_const",
        const="development",
        dest="mode",
        help="Create a development build",
    )
    mode.add_argument(
        "--production",
        action="store_const",
        const="production",
        dest="mode",
        help="Create a production build",
    )
    mode.add_argument(
        "--profiling",
        action="store_const",
        const="profiling",
        dest="mode",
        help="Create a profiling build",
    )
    mode.set_defaults(mode="production")

    parser.add_argument(
        "--update", action="store_true", help="Run `npm update` before building"
    )
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="Stop after running `npm install`/`npm update`",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Run `npm run build` even if build output already exists",
    )
    parser.add_argument("--prefix", help="Path prefix of new UI")
    parser.add_argument(
        "--compress",
        choices=compression_choices,
        action="append",
        help=(
            "Generate compressed versions of all static .js, .css and .map " "files."
        ),
    )
    parser.add_argument("--install", metavar="HOME_DIR", help="Install static UI files")

    archive_group = parser.add_argument_group("Archive creation options")
    archive_group.add_argument(
        "--archive-type",
        choices={"tar.gz", "tar.xz", "zip"},
        default=[],
        action="append",
        help="Archive type",
    )
    archive_group.add_argument(
        "--archive-dir",
        help=(
            "Directory to store archive in. The filename will be "
            "`ui-{hash}.{type}` where `hash` is the hash of the resulting "
            "archive file and `type` depends on `--archive-type`."
        ),
    )

    s3_group = parser.add_argument_group("Cloud (AWS S3) options")
    s3_group.add_argument("--upload", action="store_true", help="Upload to the cloud")
    s3_group.add_argument(
        "--s3-bucket", default="ui.critic-review.org", help="Bucket name"
    )
    s3_group.add_argument(
        "--s3-storage-class", default="REDUCED_REDUNDANCY", help="Storage class"
    )

    executables_group = parser.add_argument_group("Executables")
    executables_group.add_argument(
        "--with-npm",
        metavar="PATH",
        help="`npm` executable",
        dest="npm",
        **executable_argument("npm"),
    )

    arguments = parser.parse_args()

    if not os.path.isdir(os.path.join(UI_DIR, "node_modules")):
        subprocess.check_call([arguments.npm, "install"], cwd=UI_DIR)
    elif arguments.update:
        subprocess.check_call([arguments.npm, "update"], cwd=UI_DIR)

    if arguments.no_build:
        return

    package_json = os.path.join(UI_DIR, "package.json")
    with open(package_json, "r", encoding="utf-8") as file:
        package = json.load(file)
    if arguments.prefix:
        package["homepage"] = arguments.prefix
    elif "homepage" in package:
        del package["homepage"]
    with open(package_json, "w", encoding="utf-8") as file:
        print(json.dumps(package, indent=2), file=file)

    config_json = os.path.join(UI_DIR, "src", "config.json")
    with open(config_json, "w", encoding="utf-8") as file:
        json.dump({"fetchDefaultOptions": {"credentials": "same-origin"}}, file)

    build_dir = UI_DIR / "dist"

    if not (build_dir / "index.html").is_file() or arguments.rebuild:
        subprocess.check_call(
            [arguments.npm, "run-script", f"build-{arguments.mode}"], cwd=UI_DIR
        )

    if arguments.compress:
        build_static_dir = build_dir / "static"
        pool = multiprocessing.Pool()

        def compress_done(result: Tuple[Algorithm, Path, float]) -> None:
            _, compressed_path, ratio = result
            print(
                "Compressed %s: %.2f %%"
                % (compressed_path.relative_to(build_dir), 100 * ratio)
            )

        for path in build_static_dir.glob(COMPRESS_GLOB):
            print(path)
            for algorithm in arguments.compress:
                pool.apply_async(compress, (algorithm, path), callback=compress_done)

        pool.close()
        pool.join()

    for archive_type in arguments.archive_type:
        archive_file = io.BytesIO()

        def add_files(add: Callable[[str], None]) -> None:
            add("favicon.png")
            add("index.html")
            add("static/css/*.css")
            add("static/css/*.css.gz")
            add("static/js/*.js")
            add("static/js/*.js.gz")
            add("static/media/icons.*")
            add("static/media/outline-icons.*")

        if archive_type in ("tar.gz", "tar.xz"):
            mode = "w:gz" if archive_type == "tar.gz" else "w:xz"

            def add_tar(archive: TarFile, pattern: str) -> None:
                for path in (build_dir / pattern).glob(pattern):
                    archive.add(
                        path, os.path.join("ui", os.path.relpath(path, build_dir))
                    )

            with tarfile.open(mode=mode, fileobj=archive_file) as archive:
                add_files(functools.partial(add_tar, archive))
        else:

            def add_zip(archive: ZipFile, pattern: str) -> None:
                for path in (build_dir / pattern).glob(pattern):
                    filename = os.path.join("ui", os.path.relpath(path, build_dir))
                    _, _, ext = filename.rpartition(".")
                    if ext in EXTENSIONS_TO_STORE:
                        compress_type = zipfile.ZIP_STORED
                    else:
                        compress_type = zipfile.ZIP_LZMA
                    archive.write(path, filename, compress_type)

            with zipfile.ZipFile(archive_file, "w") as archive:
                add_files(functools.partial(add_zip, archive))

        archive_contents = archive_file.getvalue()
        sha256_digest = hashlib.sha256(archive_contents).hexdigest()

        archive_dir = arguments.archive_dir or os.getcwd()
        archive_filename = f"ui-{sha256_digest}.{archive_type}"
        archive_path = os.path.join(archive_dir, archive_filename)

        with open(archive_path, "wb") as file:
            file.write(archive_contents)

        print(f"Created {archive_path}")

    if arguments.upload:
        try:
            import boto3 as _
        except ModuleNotFoundError:
            print("You need to install `boto3` to upload!")
            return 1

        md5_digest = base64.b64encode(hashlib.md5(archive_contents).digest()).decode()

        s3 = boto3.client("s3")
        s3_location = s3.get_bucket_location(Bucket=arguments.s3_bucket)
        s3_region = s3_location["LocationConstraint"]

        ui_json = os.path.join(DATA_DIR, "ui.json")
        with open(ui_json, "w", encoding="utf-8") as file:
            print(
                json.dumps(
                    {
                        "cloud": "Amazon S3",
                        "bucket": {"region": s3_region, "name": arguments.s3_bucket},
                        "archive": {
                            "name": archive_filename,
                            "size": len(archive_contents),
                            "sha256": sha256_digest,
                        },
                    }
                ),
                file=file,
            )

        s3.put_object(
            ACL="public-read",
            Body=archive_file,
            Bucket=arguments.s3_bucket,
            ContentMD5=md5_digest,
            Key=archive_filename,
            StorageClass=arguments.s3_storage_class,
        )

    if arguments.install:
        install_dir = Path(arguments.install) / "ui"

        if not os.path.isdir(install_dir):
            os.makedirs(install_dir)

        shutil.copy2((build_dir / "index.html"), install_dir)

        static_install_dir = install_dir / "static"

        if os.path.isdir(static_install_dir):
            shutil.rmtree(static_install_dir)

        shutil.copytree((build_dir / "static"), static_install_dir)


if __name__ == "__main__":
    sys.exit(main() or 0)
