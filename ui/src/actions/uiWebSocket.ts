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

import { showToast } from "./uiToast"
import {
  WEB_SOCKET_CONNECTED,
  WEB_SOCKET_DISCONNECTED,
  Action,
  SUBSCRIBE_TO_CHANNEL,
  WebSocketListener,
  UNSUBSCRIBE_FROM_CHANNEL,
  ADD_WEB_SOCKET_LISTENER,
  REMOVE_WEB_SOCKET_LISTENER,
  ChannelCallback,
} from "."
import { Dispatch, GetState } from "../state"

export const webSocketConnected = (connection: WebSocket): Action => ({
  type: WEB_SOCKET_CONNECTED,
  connection,
})

export const webSocketDisconnected = (): Action => ({
  type: WEB_SOCKET_DISCONNECTED,
})

export const addListener = (listener: WebSocketListener): Action => ({
  type: ADD_WEB_SOCKET_LISTENER,
  listener,
})

export const removeListener = (listener: WebSocketListener): Action => ({
  type: REMOVE_WEB_SOCKET_LISTENER,
  listener,
})

export const connectWebSocket = () => (
  dispatch: Dispatch,
  getState: GetState,
) => {
  const prefix = window.location.origin.replace(/^http(s?):/, "ws$1:")
  const connection = new WebSocket(`${prefix}/ws`, ["pubsub_1"])

  connection.onopen = () => {
    dispatch(webSocketConnected(connection))

    const { webSocket } = getState().ui
    const channels = webSocket.channels.keySeq().toJS()
    if (channels.length)
      connection.send(
        JSON.stringify({
          subscribe: channels,
        }),
      )
  }

  connection.onclose = ({ code }) => {
    const wasConnected = getState().ui.webSocket.connection !== null
    dispatch(webSocketDisconnected())
    switch (code) {
      case 1006:
        // "Abnormal Closure", like the server not handling web sockets at all.
        if (wasConnected) {
          dispatch(
            showToast({
              type: "error",
              title: "WebSocket failed!",
            }),
          )
        }
        setTimeout(() => dispatch(connectWebSocket()), 10000)
        return

      default:
        setTimeout(() => dispatch(connectWebSocket()), 1000)
    }
  }

  connection.onmessage = ({ data }) => {
    const { listeners, channels } = getState().ui.webSocket
    const payload = JSON.parse(data)

    const listenersToRemove = []
    for (const listener of listeners)
      if (listener(payload) === "remove") listenersToRemove.push(listener)
    for (const listener of listenersToRemove) dispatch(removeListener(listener))

    if (payload.publish) {
      const { channel, message } = payload.publish
      const callbacks = channels.get(channel, [])
      for (const callback of callbacks) callback(channel, message)
    }
  }
}

export const subscribeToChannel = (
  channel: string,
  callback: ChannelCallback,
) => (dispatch: Dispatch, getState: GetState) =>
  new Promise<boolean>((resolve) => {
    const { webSocket } = getState().ui
    const alreadySubscribed = webSocket.channels.has(channel)

    dispatch({
      type: SUBSCRIBE_TO_CHANNEL,
      channel,
      callback,
    })

    if (alreadySubscribed) {
      resolve(false)
    } else {
      dispatch(
        addListener((payload: { subscribed?: string[] }) => {
          if (payload.subscribed && payload.subscribed.includes(channel)) {
            resolve(true)
            return "remove"
          }
        }),
      )

      if (webSocket.connection)
        webSocket.connection.send(JSON.stringify({ subscribe: channel }))
    }
  })

export const unsubscribeFromChannel = (
  channel: string,
  callback: ChannelCallback,
) => (dispatch: Dispatch, getState: GetState) =>
  new Promise((resolve) => {
    dispatch({
      type: UNSUBSCRIBE_FROM_CHANNEL,
      channel,
      callback,
    })

    const { webSocket } = getState().ui
    if (webSocket.connection && !webSocket.channels.has(channel)) {
      dispatch(
        addListener((payload) => {
          if (payload.unsubscribed && payload.unsubscribed.includes(channel)) {
            resolve(true)
            return "remove"
          }
        }),
      )

      webSocket.connection.send(JSON.stringify({ unsubscribe: channel }))
    } else resolve(false)
  })
