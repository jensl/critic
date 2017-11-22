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

import Immutable from "immutable"

import {
  UIAddon,
  REGISTER_UI_ADDON,
  UNREGISTER_UI_ADDON,
  ADD_EXTENSION_PAGE,
  /* ADD_NAVIGATION_ITEM,
  ADD_REVIEW_NOTICE, */
  ADD_EXTENSION_LINKIFIER,
  Action,
  RenderPageFunc,
  GenerateURLFunc,
  RenderLinkFunc,
} from "../actions"

class State extends Immutable.Record<{
  uiAddonStates: Immutable.Map<string, UIAddonState>
}>({
  uiAddonStates: Immutable.Map(),
}) {}

const InvalidUIAddon = (null as unknown) as UIAddon

class UIAddonState extends Immutable.Record<{
  uiAddon: UIAddon
  pages: Immutable.List<Page>
  linkifiers: Immutable.List<Linkifier>
}>({
  uiAddon: InvalidUIAddon,
  /* navigationItems: Immutable.List(),
  reviewNotices: Immutable.List(), */
  pages: Immutable.List(),
  linkifiers: Immutable.List(),
}) {}

/* class ReviewCard extends Immutable.Record<{}>({
  extension: null,
  render: null,
}) {} */

class Page extends Immutable.Record<{
  uiAddon: UIAddon
  path: string
  render: RenderPageFunc
}>({
  uiAddon: InvalidUIAddon,
  path: "",
  render: () => null,
}) {}

/* class NavigationItem extends Immutable.Record<{}>({
  component: null,
}) {}

class ReviewNotice extends Immutable.Record<{}>({
  component: null,
}) {} */

class Linkifier extends Immutable.Record<{
  pattern: string
  regexp: RegExp
  generateURL: GenerateURLFunc | null
  render: RenderLinkFunc | null
}>({
  pattern: "",
  regexp: /(?:)/,
  generateURL: null,
  render: null,
}) {}

type UIAddonAction = { uiAddon: UIAddon }

export const extension = (state = new State(), action: Action) => {
  const uiAddonState = <T extends UIAddonAction>(action: T) =>
    state.uiAddonStates.get(action.uiAddon.key)!

  switch (action.type) {
    case REGISTER_UI_ADDON:
      return state.set(
        "uiAddonStates",
        state.uiAddonStates.set(action.uiAddon.key, new UIAddonState(action))
      )
    case UNREGISTER_UI_ADDON:
      return state.set(
        "uiAddonStates",
        state.uiAddonStates.delete(action.uiAddon.key)
      )

    /* case ADD_NAVIGATION_ITEM:
      return state.setIn(
        ["uiAddonStates", action.uiAddon.key, "navigationItems"],
        uiAddonState.navigationItems.push(new NavigationItem(action))
      )

    case ADD_REVIEW_NOTICE:
      return state.setIn(
        ["uiAddonStates", action.uiAddon.key, "reviewNotices"],
        uiAddonState.reviewNotices.push(new ReviewNotice(action))
      ) */

    case ADD_EXTENSION_PAGE:
      return state.setIn(
        ["uiAddonStates", action.uiAddon.key, "pages"],
        uiAddonState(action).pages.push(new Page(action))
      )

    case ADD_EXTENSION_LINKIFIER:
      return state.setIn(
        ["uiAddonStates", action.uiAddon.key, "linkifiers"],
        uiAddonState(action).linkifiers.push(new Linkifier(action))
      )

    default:
      return state
  }
}
