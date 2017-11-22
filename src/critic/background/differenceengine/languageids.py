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

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

logger = logging.getLogger(__name__)

from critic import api


class LanguageIds:
    async def update(
        self, critic: api.critic.Critic, language_mappings: Mapping[str, Any]
    ) -> None:
        async with critic.query("SELECT id, label FROM highlightlanguages") as result:
            self.per_id = dict(await result.all())
        self.per_label = {
            label: language_id for language_id, label in self.per_id.items()
        }
        missing_labels = set()
        for label in language_mappings.keys():
            if label not in self.per_label:
                missing_labels.add(label)
        if missing_labels:
            async with critic.transaction() as cursor:
                for label in missing_labels:
                    async with cursor.query(
                        """INSERT
                            INTO highlightlanguages (
                                    label
                                ) VALUES (
                                    {label}
                                )""",
                        label=label,
                        returning="id",
                    ) as result:
                        langugage_id = await result.scalar()
                    self.per_label[label] = langugage_id
                    self.per_id[langugage_id] = label

    def get_id(self, language_label: str) -> Optional[int]:
        if language_label is None:
            return None
        return self.per_label[language_label]

    def get_label(self, language_id: int) -> Optional[str]:
        if language_id is None:
            return None
        return self.per_id[language_id]
