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
  uri: string
  versions: ExtensionVersionID[]
  installation: ExtensionInstallationID | null
}

type ExtensionProps = ExtensionData

class Extension {
  constructor(
    readonly id: ExtensionID,
    readonly name: string,
    readonly key: string,
    readonly publisher: UserID,
    readonly uri: string,
    readonly versions: ExtensionVersionID[],
    readonly installation: ExtensionInstallationID | null
  ) {}

  static new(props: ExtensionProps) {
    return new Extension(
      props.id,
      props.name,
      props.key,
      props.publisher,
      props.uri,
      props.versions,
      props.installation
    )
  }

  static reducer = combineReducers({
    byID: primaryMap<Extension, ExtensionID>("extensions"),
    byKey: lookupMap<Extension, string, ExtensionID>(
      "extensions",
      (extension) => extension.key
    ),
  })

  get props(): ExtensionProps {
    return this
  }
}

export default Extension
