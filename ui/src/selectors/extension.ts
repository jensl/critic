/*
 * Copyright 2017 the Critic contributors, Opera Software ASA
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may not
 * use this file except in compliance with the License.  You may obtain a copy
 * of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
 * License for the specific language governing permissions and limitations under
 * the License.
 */

import { castImmutable } from "immer"
import { createSelector } from "reselect"
import Extension from "../resources/extension"
import { State } from "../state"
import ExtensionVersion from "../resources/extensionversion"
import { ExtensionID } from "../resources/types"

type ExtensionProp = { extension: Extension }
type ExtensionIDProp = { extensionID: ExtensionID }
type GetExtensionProps = ExtensionProp | ExtensionIDProp

const isExtensionProp = (props: GetExtensionProps): props is ExtensionProp =>
  "extension" in props

export const getExtension = (state: State, props: GetExtensionProps) =>
  isExtensionProp(props)
    ? props.extension
    : state.resource.extensions.byID.get(props.extensionID)

const getExtensionVersions = (state: State) => state.resource.extensionversions

export const getVersionsPerExtension = createSelector(
  getExtensionVersions,
  (versions) => {
    const result = new Map<ExtensionID, Set<ExtensionVersion>>()
    for (const version of versions.values()) {
      const extensionID = version.extension
      let perExtension = result.get(extensionID)
      if (!perExtension)
        result.set(extensionID, (perExtension = new Set<ExtensionVersion>()))
      perExtension.add(version)
    }
    return castImmutable(result)
  },
)

export const getVersionsForExtension = createSelector(
  getVersionsPerExtension,
  getExtension,
  (versionsPerExtension, extension) =>
    extension ? versionsPerExtension.get(extension.id) : null,
)

export const getCurrentVersions = createSelector(
  getExtensionVersions,
  getExtension,
  (versions, extension) =>
    extension
      ? new Map(
          extension.versions
            .map((versionID): [string, ExtensionVersion] | null => {
              const version = versions.get(versionID)
              return version ? [version.name, version] : null
            })
            .filter((entry) => entry !== null) as [string, ExtensionVersion][],
        )
      : null,
)
