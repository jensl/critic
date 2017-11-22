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

import { fetchUIAddon } from "./extension"
import { createUIAddon } from "../utils/Extension"
import {
  UIAddon,
  REGISTER_UI_ADDON,
  UNREGISTER_UI_ADDON,
  ADD_EXTENSION_LINKIFIER,
  GenerateURLFunc,
  RenderLinkFunc,
  ADD_EXTENSION_PAGE,
  RenderPageFunc,
  RegisterUIAddonAction,
  UnregisterUIAddonAction,
  AddExtensionPageAction,
  AddExtensionLinkifierAction,
} from "../actions"
import Extension from "../resources/extension"
import ExtensionInstallation from "../resources/extensioninstallation"
import { Thunk } from "../state"

export const registerUIAddon = (uiAddon: UIAddon): RegisterUIAddonAction => ({
  type: REGISTER_UI_ADDON,
  uiAddon,
})

export const unregisterUIAddon = (
  uiAddon: UIAddon
): UnregisterUIAddonAction => ({
  type: UNREGISTER_UI_ADDON,
  uiAddon,
})

export const installUIAddon = (
  extension: Extension,
  installation: ExtensionInstallation,
  { name, has_js, has_css }: { name: string; has_js: boolean; has_css: boolean }
): AsyncThunk<void> => async (dispatch) => {
  if (has_js) {
    const source = await dispatch(fetchUIAddon(extension, name, "js"))
    const uiAddon = await createUIAddon(extension, installation, name, source)
    dispatch(registerUIAddon(uiAddon)) // FIXME
    uiAddon.install()
  }
}

export const uninstallUIAddon = (uiAddon: UIAddon): AsyncThunk<void> => async (
  dispatch
) => {
  uiAddon.uninstall()
  dispatch(unregisterUIAddon(uiAddon))
}

/* export const ADD_REVIEW_CARD = "ADD_REVIEW_CARD"
export const addReviewCard = (extension, component) => ({
  type: ADD_REVIEW_CARD,
  extension,
  component,
}) */

/* export const ADD_NAVIGATION_ITEM = "ADD_NAVIGATION_ITEM"
export const addNavigationItem = (uiAddon, component) => ({
  type: ADD_NAVIGATION_ITEM,
  uiAddon,
  component,
})

export const ADD_REVIEW_NOTICE = "ADD_REVIEW_NOTICE"
export const addReviewNotice = (uiAddon, component) => ({
  type: ADD_REVIEW_NOTICE,
  uiAddon,
  component,
}) */
