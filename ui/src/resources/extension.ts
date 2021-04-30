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

import { combineReducers } from "redux"
import { immerable } from "immer"

import { lookupMap, primaryMap } from "../reducers/resource"
import {
  ExtensionID,
  UserID,
  ExtensionVersionID,
  ExtensionInstallationID,
} from "./types"

type ExtensionData = {
  id: ExtensionID
  name: string
  key: string
  publisher: UserID
  url: string
  versions: ExtensionVersionID[]
  default_version: ExtensionVersionID
  installation: ExtensionInstallationID | null
}

type ExtensionProps = {
  id: ExtensionID
  name: string
  key: string
  publisher: UserID
  url: string
  versions: readonly ExtensionVersionID[]
  default_version: ExtensionVersionID
  installation: ExtensionInstallationID | null
}

class Extension {
  [immerable] = true

  constructor(
    readonly id: ExtensionID,
    readonly name: string,
    readonly key: string,
    readonly publisher: UserID,
    readonly url: string,
    readonly versions: readonly ExtensionVersionID[],
    readonly defaultVersion: ExtensionVersionID,
    readonly installation: ExtensionInstallationID | null,
  ) {}

  static new(props: ExtensionProps) {
    return new Extension(
      props.id,
      props.name,
      props.key,
      props.publisher,
      props.url,
      props.versions,
      props.default_version,
      props.installation,
    )
  }

  static reducer = combineReducers({
    byID: primaryMap<Extension, ExtensionID>("extensions"),
    byKey: lookupMap<Extension, string, ExtensionID>(
      "extensions",
      (extension) => extension.key,
    ),
  })

  get props(): ExtensionProps {
    return { ...this, default_version: this.defaultVersion }
  }
}

export default Extension
