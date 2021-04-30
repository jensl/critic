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
import { AsyncThunk, Dispatch, GetState } from "../state"
import { ChangesetID } from "../resources/types"
import { CompletionLevel } from "../resources/changeset"

export type CompletionLevelCallback = () => void
export type CompletionLevelCallbacks = {
  structure?: CompletionLevelCallback
  changedlines?: CompletionLevelCallback
  analysis?: CompletionLevelCallback
  syntaxhighlight?: CompletionLevelCallback
  full?: CompletionLevelCallback
}

type WebSocketMessage = {
  subscribed?: string[]
  unsubscribed?: string[]
  publish: {
    channel: string
    message: any
  }
  monitor_changeset?: {
    changeset_id: number
    completion_level: CompletionLevel[]
  }
}

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
    const channels = [...webSocket.channels.keys()]
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
      const callbacks = channels.get(channel) ?? []
      for (const callback of callbacks) callback(channel, message)
    }
  }
}

export const subscribeToChannel = (channel: string) => (
  callback: ChannelCallback,
): AsyncThunk<boolean> => (dispatch: Dispatch, getState: GetState) =>
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
        addListener((payload: WebSocketMessage) => {
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
): AsyncThunk<boolean> => (dispatch: Dispatch, getState: GetState) =>
  new Promise((resolve) => {
    dispatch({
      type: UNSUBSCRIBE_FROM_CHANNEL,
      channel,
      callback,
    })

    const { webSocket } = getState().ui
    if (webSocket.connection && !webSocket.channels.has(channel)) {
      dispatch(
        addListener((payload: WebSocketMessage) => {
          if (payload.unsubscribed && payload.unsubscribed.includes(channel)) {
            resolve(true)
            return "remove"
          }
        }),
      )

      webSocket.connection.send(JSON.stringify({ unsubscribe: channel }))
    } else resolve(false)
  })

export const monitorChangesetByID = (
  changesetID: ChangesetID,
  callbacks: CompletionLevelCallbacks,
) => (callback: ChannelCallback): AsyncThunk<boolean> => (
  dispatch: Dispatch,
  getState: GetState,
) =>
  new Promise((resolve) => {
    const { webSocket } = getState().ui
    const channel = `changesets/${changesetID}`
    const alreadySubscribed = webSocket.channels.has(channel)

    dispatch({
      type: SUBSCRIBE_TO_CHANNEL,
      channel,
      callback,
    })

    if (alreadySubscribed) {
      console.warn("already subscribed to channel", { channel })
      resolve(false)
    } else {
      dispatch(
        addListener((payload: WebSocketMessage) => {
          const monitorChangeset = payload.monitor_changeset
          if (monitorChangeset?.changeset_id === changesetID) {
            let finished = false
            for (const level of monitorChangeset.completion_level) {
              const callback = callbacks[level]
              if (callback && callback()) finished = true
            }
            if (!finished)
              dispatch(
                addListener((payload: WebSocketMessage) => {
                  const publish = payload.publish
                  if (publish)
                    if (publish.channel === channel && publish.message) {
                    }
                }),
              )
            resolve(!finished)
            return "remove"
          }
        }),
      )

      if (webSocket.connection) {
        webSocket.connection.send(
          JSON.stringify({
            monitor_changeset: {
              changeset_id: changesetID,
              required_levels: Object.keys(callbacks),
            },
          }),
        )
      } else resolve(false)
    }
  })
