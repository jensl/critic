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

import store from "../store"
import Extension from "../resources/extension"
import ExtensionInstallation from "../resources/extensioninstallation"
import {
  Action,
  UIAddon,
  RenderPageFunc,
  ADD_EXTENSION_PAGE,
  GenerateURLFunc,
  RenderLinkFunc,
  ADD_EXTENSION_LINKIFIER,
} from "../actions"
import { ExtensionID, ExtensionInstallationID } from "../resources/types"
import { useResource } from "."

const addPage = (
  uiAddon: UIAddon,
  path: string,
  render: RenderPageFunc,
): Action => ({
  type: ADD_EXTENSION_PAGE,
  uiAddon,
  path,
  render,
})

const addLinkifier = (
  uiAddon: UIAddon,
  pattern: string,
  {
    generateURL = null,
    render = null,
  }: {
    generateURL: GenerateURLFunc | null
    render: RenderLinkFunc | null
  },
): Action => ({
  type: ADD_EXTENSION_LINKIFIER,
  uiAddon,
  pattern,
  regexp: new RegExp(pattern),
  generateURL,
  render,
})

export class Critic {
  constructor(readonly uiAddon: UIAddon) {}

  addPage(path: string, render: () => JSX.Element) {
    store.dispatch(addPage(this.uiAddon, path, render))
  }

  /*
  addNavigationItem(component) {
    store.dispatch(addNavigationItem(this.uiAddon, component))
  }

  addReviewNotice(component) {
    store.dispatch(addReviewNotice(this.uiAddon, component))
  }
  */

  addLinkifier(
    pattern: string,
    {
      generateURL = null,
      render = null,
    }: {
      generateURL: ((match: string[]) => string) | null
      render: (() => JSX.Element) | null
    },
  ) {
    store.dispatch(addLinkifier(this.uiAddon, pattern, { generateURL, render }))
  }
}

interface Implementation {
  install?: (critic: Critic) => any
  uninstall?: (critic: Critic) => any
  reduce?: (state: any, action: any) => any
}

export class UIAddonHandler implements UIAddon {
  readonly key: string
  readonly critic: Critic

  constructor(
    readonly extensionID: ExtensionID,
    readonly installationID: ExtensionInstallationID,
    readonly name: string,
    readonly implementation: Implementation,
  ) {
    this.key = `${installationID}_${name}`
    this.critic = new Critic(this)
  }

  install() {
    if (this.implementation.install)
      try {
        return this.implementation.install(this.critic)
      } catch (error) {
        console.error("Extension failed!", { error })
      }
  }

  uninstall() {
    if (this.implementation.uninstall)
      try {
        return this.implementation.uninstall(this.critic)
      } catch (error) {
        console.error("Extension failed!", { error })
      }
  }

  reduce(state: any, action: any) {
    if (this.implementation.reduce)
      try {
        return this.implementation.reduce(state, action)
      } catch (error) {
        console.error("Extension failed!", { error })
      }
  }
}

export const createUIAddon = async (
  extension: Extension,
  installation: ExtensionInstallation,
  name: string,
  source: string,
) => {
  /*eslint no-new-func: "off"*/
  const fn = new Function(source)
  const scope: { extension?: any } = {}
  fn.call(scope)
  return new UIAddonHandler(
    extension.id,
    installation.id,
    name,
    new scope.extension(),
  )
}

export const useDeducedVersion = (extension: Extension | undefined) => {
  const installation = useResource("extensioninstallations", (byID) =>
    byID.get(extension?.installation ?? -1),
  )
  return useResource("extensionversions", (byID) =>
    byID.get(installation?.version ?? extension?.defaultVersion ?? -1),
  )
}
