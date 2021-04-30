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

import { immerable } from "immer"

import { primaryMap } from "../reducers/resource"
import {
  ExtensionInstallationID,
  ExtensionID,
  ExtensionVersionID,
  UserID,
} from "./types"

type ExtensionInstallationData = {
  id: ExtensionInstallationID
  extension: ExtensionID
  version: null | ExtensionVersionID
  user: null | UserID
  manifest: ManifestData
}

type ExtensionInstallationProps = {
  id: ExtensionInstallationID
  extension: ExtensionID
  version: null | ExtensionVersionID
  user: null | UserID
  manifest: Manifest
}

class ExtensionInstallation {
  [immerable] = true

  constructor(
    readonly id: ExtensionInstallationID,
    readonly extension: ExtensionID,
    readonly version: null | ExtensionVersionID,
    readonly user: null | UserID,
    readonly manifest: Manifest,
  ) {}

  static new(props: ExtensionInstallationProps) {
    return new ExtensionInstallation(
      props.id,
      props.extension,
      props.version,
      props.user,
      props.manifest,
    )
  }

  static prepare(value: ExtensionInstallationData): ExtensionInstallationProps {
    return {
      ...value,
      manifest: Manifest.make(value.manifest),
    }
  }

  static reducer = primaryMap<ExtensionInstallation, ExtensionInstallationID>(
    "extensioninstallations",
  )

  get props(): ExtensionInstallationProps {
    return this
  }
}

type ManifestData = {
  ui_addons: UIAddonData[]
}

type ManifestProps = {
  ui_addons: readonly UIAddon[]
}

class Manifest {
  [immerable] = true

  constructor(readonly ui_addons: readonly UIAddon[]) {}

  static new(props: ManifestProps) {
    return new Manifest(props.ui_addons)
  }

  static make(value: ManifestData) {
    return Manifest.new({
      ...value,
      ui_addons: value.ui_addons.map(UIAddon.new),
    })
  }
}

type UIAddonData = {
  name: string
  has_js: boolean
  has_css: boolean
}

type UIAddonProps = UIAddonData

class UIAddon {
  [immerable] = true

  constructor(
    readonly name: string,
    readonly hasJS: boolean,
    readonly hasCSS: boolean,
  ) {}

  static new(props: UIAddonProps) {
    return new UIAddon(props.name, props.has_js, props.has_css)
  }
}

export default ExtensionInstallation
