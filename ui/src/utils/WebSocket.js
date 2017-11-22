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

import {
  subscribeToChannel,
  unsubscribeFromChannel,
} from "../actions/uiWebSocket"

class Waiter {
  constructor(promise) {
    this.status = promise
  }
}

export const waitFor = async (
  dispatch,
  channel,
  { predicate = null, timeout = null } = {}
) => {
  var callback = null

  const waiter = new Waiter(
    new Promise((resolve) => {
      const finish = (status) => {
        console.debug("waitFor:finish", { status })
        dispatch(unsubscribeFromChannel(channel, callback))
        resolve(status)
      }

      const timerID =
        timeout === null ? null : setTimeout(() => finish("timeout"), timeout)

      callback = (_, message) => {
        console.debug("waitFor:message", { message })
        if (predicate !== null && !predicate(message)) return
        if (timerID !== null) clearTimeout(timerID)
        finish("success")
      }
    })
  )

  console.debug("waitFor:debug", { callback })

  await dispatch(subscribeToChannel(channel, callback))

  return waiter
}

export class Channel {
  constructor(dispatch, name) {
    this.dispatch = dispatch
    this.name = name

    this._queue = []
    this._listeners = []
    this._callback = (_, message) => {
      this._queue.push(message)
      const stillPending = []
      for (const { predicate, resolve, timeoutID } of this._listeners) {
        if (predicate(message)) {
          resolve(message)
          if (timeoutID !== null) clearTimeout(timeoutID)
        } else stillPending.push({ predicate, resolve })
      }
      this._listeners = stillPending
    }

    this.subscribed = dispatch(subscribeToChannel(name, this._callback))
  }

  waitFor(predicate, { timeout = null } = {}) {
    for (const message of this._queue) {
      if (predicate(message)) return Promise.resolve(message)
    }
    return new Promise((resolve, reject) => {
      const timeoutID =
        timeout !== null
          ? setTimeout(() => {
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
}

Channel.subscribe = async (dispatch, name) => {
  const channel = new Channel(dispatch, name)
  await channel.subscribed
  return channel
}
