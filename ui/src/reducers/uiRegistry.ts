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

import { ComponentType, FunctionComponent } from "react"

import produce from "./immer"
import { START, UIAddon } from "../actions"

type BaseComponent = ComponentType<any>

type OverrideComponentProps = {
  BaseComponent: BaseComponent
}

type OverrideComponent = ComponentType<
  { [key: string]: any } & OverrideComponentProps
>

class Component {
  override: Override | null

  constructor(readonly base: BaseComponent) {
    this.override = null
  }
}

class Override {
  constructor(
    readonly uiAddon: UIAddon,
    readonly callback: OverrideComponent,
  ) {}
}

export const baseComponents: { [key: string]: BaseComponent } = {}

export const registry = produce<Map<string, Component>>((draft, action) => {
  if (action.type === START) {
    Object.entries(baseComponents).forEach(([key, base]) =>
      draft.set(key, new Component(base)),
    )
  }
}, new Map())
