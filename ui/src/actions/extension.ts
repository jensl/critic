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

//import isomorphic_fetch from "isomorphic-fetch"

import {
  createResource,
  updateResource,
  deleteResource,
  withArgument,
  withParameters,
  include,
  fetch,
  fetchOne,
} from "../resources"

import Extension from "../resources/extension"
import ExtensionCall from "../resources/extensioncall"
import ExtensionVersion from "../resources/extensionversion"
import ExtensionInstallation from "../resources/extensioninstallation"

/*
import { fetchJSON, fetchText } from "../utils/Fetch"
import { createUIAddon } from "../utils/Extension"
import { registerUIAddon, installUIAddon } from "./uiExtension"
import { showToast } from "../actions/uiToast"
import { UserID } from "../resources/types"

export const EXTENSION_INSTALLATIONS_LOADED = "EXTENSION_INSTALLATIONS_LOADED"
const extensionInstallationsLoaded = (userID: UserID) => ({
  type: EXTENSION_INSTALLATIONS_LOADED,
  userID,
})

export const INSTALLED_EXTENSION_UPDATE = "INSTALLED_EXTENSION_UPDATE"
export const installedExtensionUpdate = (extensions) => ({
  type: INSTALLED_EXTENSION_UPDATE,
  extensions,
})

export const ADD_REVIEW_CARD = "ADD_REVIEW_CARD"
export const addReviewCard = (extension, card) => ({
  type: ADD_REVIEW_CARD,
  extension,
  card,
})

export const loadExtensions = ({
  installed = false,
  installedBy = null,
  scan = false,
}) => async (dispatch) => {
  await dispatch(
    fetch(
      "extensions",
      {
        installed_by:
          installedBy !== null ? installedBy : installed ? "(me)" : null,
        scan: scan ? "yes" : null,
      },
      {
        handleError: {
          NO_EXTENSIONS: (error) => null,
        },
      }
    )
  )
  if (installedBy) dispatch(extensionInstallationsLoaded(installedBy))
}

export const loadExtensionVersions = ({ extension }) =>
  fetch("extensionversions", { extension: extension.key })

export const loadInstalledExtensions = (userID) => async (dispatch) => {
  const { json } = await dispatch(
    fetchJSON({
      path: "extensions",
      params: {
        installed_by: userID,
      },
    })
  )

  dispatch(installedExtensionUpdate(json.extensions))

  for (const extension of json.extensions) {
    for (const ui_addon of extension.ui_addons) {
      dispatch(fetchUIAddon(extension, ui_addon))
    }
  }
}

export const fetchUIAddon = (extension, name, bundleType) => async (
  dispatch
) => {
  const response = await dispatch(
    fetchText({ path: `api/x/${extension.name}/uiaddon/${name}/${bundleType}` })
  )
  if (response.status !== 200) {
    showToast({
      type: "error",
      title: "Extension error",
      content: "Failed to load extension UI addon: " + name,
    })
    return
  }
  return await response.text()
}
*/

export const loadExtensions = () => fetch("extensions")

export const loadExtensionByKey = (key: string) =>
  fetchOne(
    "extensions",
    withParameters({ key }),
    include("extensioninstallations"),
  )

export const loadExtensionCallsByVersion = (version: ExtensionVersion) =>
  fetch("extensioncalls", withParameters({ version: version.id }))

export const loadExtensionInstallations = () => fetch("extensioninstallations")

export const installExtension = (
  extension: Extension,
  version: ExtensionVersion | null,
  universal: boolean,
) =>
  createResource(
    "extensioninstallations",
    {
      extension: extension.id,
      version: version ? version.id : null,
      universal,
    },
    {
      include: ["extensions"],
    },
  )

export const upgradeInstallation = (
  installation: ExtensionInstallation,
  version: ExtensionVersion,
) =>
  updateResource(
    "extensioninstallations",
    {
      version: version ? version.id : null,
    },
    withArgument(installation.id),
  )

export const uninstallExtension = (installation: ExtensionInstallation) =>
  deleteResource(
    "extensioninstallations",
    withArgument(installation.id),
    include("extensions"),
  )

export const createExtension = (name: string, url: string) =>
  createResource("extensions", { name, url })

export const deleteExtension = (extension: Extension) =>
  deleteResource("extensions", withArgument(extension.id))

export const repeatExtensionCall = (call: ExtensionCall) =>
  createResource("extensioncalls", { repeat: call.id })
