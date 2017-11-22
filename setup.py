# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2017 the Critic contributors, Opera Software ASA
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

from setuptools import setup, find_packages

try:
    with open("README.rst", "r", encoding="utf-8") as file:
        README_rst = file.read().splitlines()
except OSError:
    README_rst = [""]

with open("requirements.txt", "r", encoding="utf-8") as file:
    requirements = file.read().splitlines()

setup(
    name="critic",
    version="1.0.0",
    description=README_rst[0],
    long_description="\n".join(README_rst[2:]),
    url="https://critic-review.org/",
    author="The Critic contributors",
    author_email="critic-dev@critic-review.org",
    license="Apache License, Version 2.0",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Version Control",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3.6",
    ],
    # namespace_packages=["critic"],
    packages=find_packages("src", include=["critic.*"]),
    package_dir={"": "src"},
    package_data={
        "critic.data": ["*.json", "*.yaml", "dbschema/*.sql"],
        "critic.resources": [
            "*.js",
            "*.css",
            "*.png",
            "third-party/*.js",
            "third-party/*.css",
            "third-party/*.png",
            "third-party/images/*.png",
        ],
        "critic.tutorials": ["*.md", "*.txt"],
    },
    entry_points={
        "console_scripts": [
            "criticctl = critic.criticctl:main",
            "pre-post-receive = critic.hooks.pre_post_receive:main",
            "run-native-extension = critic.extension._impl.run:main",
        ]
    },
    python_requires="~=3.8",
    install_requires=[
        "aiohttp",
        "aiopg",
        "msgpack-python",
        "multidict",
        "pyyaml",
        "sshpubkeys",
    ],
    zip_safe=True,
)
