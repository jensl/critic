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
import { ADD_ITEM_TO_LIST, ItemList } from "../actions"
import { ExtensionID } from "../resources/types"

import produce from "./immer"

class Item {
  [immerable] = true

  constructor(
    readonly extensionID: ExtensionID,
    readonly itemID: string,
    readonly render: React.FunctionComponent<{}>,
    readonly before: string | null,
    readonly after: string | null,
  ) {}
}

const itemLists = produce<Map<ItemList, Item[]>>((draft, action) => {
  if (action.type === ADD_ITEM_TO_LIST) {
    const { list, extensionID, itemID, render, before, after } = action
    let items = draft.get(list)
    if (!items) draft.set(list, (items = []))
    items.push(new Item(extensionID, itemID, render, before, after))
  }
}, new Map())

export default itemLists
