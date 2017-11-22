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
  WEB_SOCKET_CONNECTED,
  WEB_SOCKET_DISCONNECTED,
  SUBSCRIBE_TO_CHANNEL,
  UNSUBSCRIBE_FROM_CHANNEL,
  ADD_WEB_SOCKET_LISTENER,
  REMOVE_WEB_SOCKET_LISTENER,
  ChannelCallback,
  WebSocketListener,
  Action,
} from "../actions"

type Props = {
  connection: WebSocket | null
  channels: Immutable.Map<string, Immutable.Set<ChannelCallback>>
  listeners: Immutable.Set<WebSocketListener>
}

class State extends Immutable.Record<Props>({
  connection: null,
  channels: Immutable.Map(),
  listeners: Immutable.Set(),
}) {}

const reducer = (state = new State(), action: Action) => {
  switch (action.type) {
    case WEB_SOCKET_CONNECTED:
      return state.set("connection", action.connection)

    case WEB_SOCKET_DISCONNECTED:
      return state.set("connection", null)

    case SUBSCRIBE_TO_CHANNEL:
      const callbacks = state.channels.get(action.channel, Immutable.Set())
      return state.setIn(
        ["channels", action.channel],
        callbacks.add(action.callback)
      )

    case UNSUBSCRIBE_FROM_CHANNEL:
      if (state.channels.has(action.channel)) {
        const callbacks = state.channels
          .get(action.channel)!
          .delete(action.callback)
        if (callbacks.size !== 0)
          state = state.setIn(["channels", action.channel], callbacks)
        else state = state.deleteIn(["channels", action.channel])
      }
      return state

    case ADD_WEB_SOCKET_LISTENER:
      return state.updateIn(["listeners"], (listeners) =>
        listeners.add(action.listener)
      )

    case REMOVE_WEB_SOCKET_LISTENER:
      return state.updateIn(["listeners"], (listeners) =>
        listeners.delete(action.listener)
      )

    default:
      return state
  }
}

export default reducer
