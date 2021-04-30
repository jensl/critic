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

import { ChannelCallback, SubscribeToChannelAction } from "../actions"
import {
  monitorChangesetByID,
  subscribeToChannel,
  unsubscribeFromChannel,
  CompletionLevelCallbacks,
} from "../actions/uiWebSocket"
import { assertNotNull } from "../debug"
import Changeset, { CompletionLevel } from "../resources/changeset"
import { ChangesetID } from "../resources/types"
import { AsyncThunk, Dispatch } from "../state"

type Status = "success" | "timeout"

// type WaitForOptions = {
//   predicate?: (message: unknown) => boolean
//   timeout?: number
// }

// class Waiter {
//   constructor(readonly promise: Promise<Status>) {}
// }

// export const waitFor = async (
//   dispatch: Dispatch,
//   channel: string,
//   { predicate, timeout }: WaitForOptions = {},
// ) => {
//   let callback: ChannelCallback | null = null

//   const waiter = new Waiter(
//     new Promise((resolve) => {
//       const finish = (status: Status) => {
//         console.debug("waitFor:finish", { status })
//         dispatch(unsubscribeFromChannel(channel, callback!))
//         resolve(status)
//       }

//       const timerID =
//         typeof timeout === "number"
//           ? window.setTimeout(() => finish("timeout"), timeout)
//           : null

//       callback = (_, message) => {
//         console.debug("waitFor:message", { message })
//         if (predicate && !predicate(message)) return
//         if (timerID !== null) clearTimeout(timerID)
//         finish("success")
//       }
//     }),
//   )

//   console.debug("waitFor:debug", { callback })

//   assertNotNull(callback)
//   await dispatch(subscribeToChannel(channel, callback))

//   return waiter
// }

type Predicate = (message: unknown) => boolean
type Options = { timeout?: number }

type Listener = {
  predicate: Predicate
  resolve: (message: unknown) => void
  timeoutID: number | null
}

export class Channel {
  _queue: unknown[]
  _listeners: Listener[]
  _callback: (channel: string, message: unknown) => void
  subscribed: Promise<boolean>

  constructor(
    readonly dispatch: Dispatch,
    readonly name: string,
    action: (callback: ChannelCallback) => AsyncThunk<boolean>,
  ) {
    this._queue = []
    this._listeners = []
    this._callback = (_, message: unknown) => {
      console.log("Channel callback", { message })
      this._queue.push(message)
      const stillPending = []
      for (const { predicate, resolve, timeoutID } of this._listeners) {
        console.log("Channel callback", { predicate })
        if (predicate(message)) {
          resolve(message)
          if (timeoutID !== null) clearTimeout(timeoutID)
        } else stillPending.push({ predicate, resolve, timeoutID })
      }
      this._listeners = stillPending
    }

    this.subscribed = dispatch(action(this._callback))
  }

  waitFor(predicate: Predicate, { timeout }: Options = {}) {
    console.log("Channel.waitFor", { predicate, timeout, queue: this._queue })
    for (const message of this._queue) {
      if (predicate(message)) return Promise.resolve(message)
    }
    return new Promise((resolve, reject) => {
      const timeoutID =
        typeof timeout === "number"
          ? window.setTimeout(() => {
              try {
                this._listeners.forEach((listener, index) => {
                  if (timeoutID === listener.timeoutID) throw index
                })
              } catch (index) {
                this._listeners.splice(index, 1)
                reject("timeout")
              }
            }, timeout)
          : null
      this._listeners.push({ predicate, resolve, timeoutID })
    })
  }

  close() {
    return this.dispatch(unsubscribeFromChannel(this.name, this._callback))
  }

  static subscribe = (name: string): AsyncThunk<Channel> => async (
    dispatch,
  ) => {
    const channel = new Channel(dispatch, name, subscribeToChannel(name))
    await channel.subscribed
    return channel
  }

  static monitorChangeset = (
    changesetID: ChangesetID,
    callbacks: CompletionLevelCallbacks,
  ): AsyncThunk<Channel | null> => async (dispatch) => {
    const channel = new Channel(
      dispatch,
      `changesets/${changesetID}`,
      monitorChangesetByID(changesetID, callbacks),
    )
    const isSubscribed = await channel.subscribed
    return isSubscribed ? channel : null
  }
}
