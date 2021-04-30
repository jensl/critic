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

import { Draft, immerable } from "immer"

import {
  WEB_SOCKET_CONNECTED,
  WEB_SOCKET_DISCONNECTED,
  SUBSCRIBE_TO_CHANNEL,
  UNSUBSCRIBE_FROM_CHANNEL,
  ADD_WEB_SOCKET_LISTENER,
  REMOVE_WEB_SOCKET_LISTENER,
  ChannelCallback,
  WebSocketListener,
} from "../actions"
import produce from "./immer"

class State {
  [immerable] = true

  constructor(
    readonly connection: WebSocket | null,
    readonly channels: ReadonlyMap<string, ReadonlySet<ChannelCallback>>,
    readonly listeners: ReadonlySet<WebSocketListener>,
  ) {}

  static default() {
    return new State(null, new Map(), new Set())
  }
}

const getOrCreateChannel = (draft: Draft<State>, name: string) => {
  const existing = draft.channels.get(name)
  if (existing) return existing
  const created: Set<ChannelCallback> = new Set()
  draft.channels.set(name, created)
  return created
}

const reducer = produce<State>((draft, action) => {
  switch (action.type) {
    case WEB_SOCKET_CONNECTED:
      draft.connection = action.connection
      break

    case WEB_SOCKET_DISCONNECTED:
      draft.connection = null
      break

    case SUBSCRIBE_TO_CHANNEL:
      const callbacks = getOrCreateChannel(draft, action.channel)
      callbacks.add(action.callback)
      break

    case UNSUBSCRIBE_FROM_CHANNEL:
      const channel = draft.channels.get(action.channel)
      if (channel) {
        if (channel.delete(action.callback) && channel.size === 0)
          draft.channels.delete(action.channel)
      }
      break

    case ADD_WEB_SOCKET_LISTENER:
      draft.listeners.add(action.listener)
      break

    case REMOVE_WEB_SOCKET_LISTENER:
      draft.listeners.delete(action.listener)
      break
  }
}, State.default())

export default reducer
