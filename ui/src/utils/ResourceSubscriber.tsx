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

import React, { useContext, useEffect } from "react"
import Immutable from "immutable"
import isArray from "lodash/isArray"
import isEqual from "lodash/isEqual"
import isPlainObject from "lodash/isPlainObject"
import map from "lodash/map"
import values from "lodash/values"
import flatten from "lodash/flatten"

import { useDispatch } from "../store"
import Token from "./Token"
import { AsyncThunk, Dispatch, Thunk } from "../state"
import { filterInPlace, soon } from "./Functions"
import { assertNotNull } from "../debug"
import { ShortcutScope } from "./KeyboardShortcuts"

type FetchCallback<T extends any[] = any> = (
  ...args: T
) => Thunk<any> | AsyncThunk<any>

type Subscription = {
  fetch: FetchCallback
  args: any[]
  tokens: Set<Token>
}

type RemoveSubscriberCallback = () => void

class ResourceSubscriptionsState {
  map: Map<FetchCallback, Subscription[]>
  pruneScheduled: boolean

  constructor(readonly dispatch: Dispatch) {
    this.map = new Map()
    this.pruneScheduled = false
  }

  ensureSubscription<T extends any[]>(
    fetch: FetchCallback<T>,
    args: T,
  ): Subscription {
    let subscriptions = this.map.get(fetch)
    if (!subscriptions) this.map.set(fetch, (subscriptions = []))
    let subscription = subscriptions.find((subscription) =>
      isEqual(subscription.args, args),
    )
    if (!subscription) {
      console.debug("New subscription", { fetch: fnName(fetch), args })
      subscriptions.push((subscription = { fetch, args, tokens: new Set() }))
      this.dispatch(fetch(...args))
    }
    return subscription
  }

  addSubscriber<T extends any[]>(
    fetch: FetchCallback<T>,
    args: T,
  ): RemoveSubscriberCallback {
    const token = Token.create()
    console.debug("New subscriber", { fetch: fnName(fetch), args, token })
    const subscription = this.ensureSubscription(fetch, args)
    subscription.tokens.add(token)
    return () => {
      console.debug("Removing subscriber", {
        fetch: fnName(fetch),
        args,
        token,
      })
      subscription.tokens.delete(token)
      if (subscription.tokens.size === 0) this.prune()
    }
  }

  prune(): void {
    if (!this.pruneScheduled) {
      this.pruneScheduled = true
      soon(() => {
        const empty: Set<FetchCallback> = new Set()
        for (const [fetch, subscriptions] of this.map.entries()) {
          filterInPlace(subscriptions, (subscription) => {
            if (subscription.tokens.size === 0)
              console.debug("Pruning subscription", {
                fetch: fnName(fetch),
                args: subscription.args,
              })
            return subscription.tokens.size !== 0
          })
          if (subscriptions.length === 0) empty.add(fetch)
        }
        for (const fetch of empty) this.map.delete(fetch)
        this.pruneScheduled = false
      })
    }
  }

  reload(): void {
    for (const [fetch, subscriptions] of this.map.entries()) {
      for (const subscription of subscriptions)
        this.dispatch(fetch(...subscription.args))
    }
  }
}

const ResourceSubscriptionsContext = React.createContext<ResourceSubscriptionsState | null>(
  null,
)

function dependencies<T extends any[]>(arg: T): T
function dependencies<T extends {}>(arg: T): any[]
function dependencies<T>(arg: T): T[]

function dependencies(arg: any): any[] {
  if (isArray(arg)) return flatten(map(arg, dependencies))
  if (isPlainObject(arg)) return flatten(map(values(arg), dependencies))
  if (Immutable.isRecord(arg) && arg.has("id")) return [arg.get("id")]
  return [arg]
}

const fnName = (fn: any) => fn.name ?? String(fn)

export const useSubscription = <T extends any[]>(
  fetch: FetchCallback<T>,
  ...args: T
) => useSubscriptionIf(true, fetch, ...args)

export const useSubscriptionIf = <T extends any[]>(
  predicate: boolean | ((...args: T) => boolean),
  fetch: FetchCallback<T>,
  ...args: T
) => {
  const subscriptions = useContext(ResourceSubscriptionsContext)
  assertNotNull(subscriptions)
  useEffect(() => {
    if (typeof predicate === "boolean") {
      if (!predicate) return
    } else if (!predicate(...args)) return
    return subscriptions.addSubscriber(fetch, args)
  }, dependencies(args)) // eslint-disable-line react-hooks/exhaustive-deps
}

const ResourceSubscriptions: React.FunctionComponent = ({ children }) => {
  const dispatch = useDispatch()
  const subscriptions = new ResourceSubscriptionsState(dispatch)
  return (
    <ResourceSubscriptionsContext.Provider value={subscriptions}>
      <ShortcutScope
        name="ResourceSubscriptions"
        handler={{
          R: () => subscriptions.reload(),
        }}
      >
        {children}
      </ShortcutScope>
    </ResourceSubscriptionsContext.Provider>
  )
}

export default ResourceSubscriptions

/*
export const useSubscription = <T extends { [key: string]: any }>(
  action: (parameters: T) => any,
  parameters: T | null,
  predicate: (parameters: T) => boolean = () => true
) => {
  const immutableParameters = Immutable.Map(parameters || {})
  useEffect(() => {
    if (parameters !== null && predicate(parameters)) {
      const token = dispatch(registerSubscriber(action, immutableParameters))
      return () =>
        dispatch(unregisterSubscriber(action, immutableParameters, token))
    }
  }, serialize(immutableParameters))
}
*/

/*
export const useSubscriptions = subscriptions => {
  const values = []
  const immutable = []
  subscriptions.forEach(({ action, parameters = {} }) => {
    parameters = new Immutable.Map(parameters)
    values.push(action, ...serialize(parameters))
    immutable.push({ action, parameters })
  })
  useEffect(() => {
    let token = null
    immutable.forEach(({ action, parameters = {} }) => {
      token = dispatch(registerSubscriber(action, parameters, token))
    })
    return () =>
      immutable.forEach(({ action, parameters = {} }) =>
        dispatch(unregisterSubscriber(action, parameters, token))
      )
  }, values)
}
*/

/*export const withSubscriptions = subscriptions => WrappedComponent => {
  class WithSubscriptions extends React.Component {
    componentDidMount() {
      this.handleWebSocketMessage = (channel, message) => this.reload()
      const [resources, channels] = this.effectiveSubscriptions()
      for (const [action, parameters] of resources) {
        dispatch(registerSubscriber(action, parameters, this))
      }
      for (const channel of channels) {
        dispatch(subscribeToChannel(channel, this.handleWebSocketMessage))
      }
      this.token = dispatch(
        pushKeyboardShortcutScope({
          name: "resource-subscriber",
          handler: event => this.handleKeyPress(event),
          scopeType: "all",
        })
      )
    }

    componentDidUpdate(prevProps) {
      const [prevResources, prevChannels] = this.effectiveSubscriptions(
        prevProps
      )
      const [nextResources, nextChannels] = this.effectiveSubscriptions()

      for (const [action, parameters] of nextResources) {
        const prevParameters = prevResources.get(action, null)
        if (Immutable.is(prevParameters, parameters)) {
          prevResources.delete(action)
        } else {
          dispatch(registerSubscriber(action, parameters, this))
        }
      }
      for (const [action, parameters] of prevResources) {
        dispatch(unregisterSubscriber(action, parameters, this))
      }

      for (const channel of nextChannels) {
        if (!prevChannels.delete(channel)) {
          dispatch(subscribeToChannel(channel, this.handleWebSocketMessage))
        }
      }
      for (const channel of prevChannels) {
        dispatch(unsubscribeFromChannel(channel, this.handleWebSocketMessage))
      }
    }

    componentWillUnmount() {
      const [resources, channels] = this.effectiveSubscriptions()
      for (const [action, parameters] of resources) {
        dispatch(unregisterSubscriber(action, parameters, this))
      }
      for (const channel of channels) {
        dispatch(unsubscribeFromChannel(channel, this.handleWebSocketMessage))
      }
      dispatch(popKeyboardShortcutScope(this.token))
    }

    handleKeyPress(event) {
      if (event.key !== "r") return false
      this.reload()
      return { preventDefault: true }
    }

    reload() {
      const [resources] = this.effectiveSubscriptions()
      for (const [action, parameters] of resources) {
        dispatch(reloadSubscription(action, parameters))
      }
    }

    effectiveSubscriptions(props = null) {
      const actualSubscriptions = subscriptions(props || this.props)
      const actions = new Set()
      const resources = []
      const channels = new Set()
      if (actualSubscriptions !== null) {
        for (const {
          action,
          parameters = {},
          channel,
        } of actualSubscriptions) {
          if (action) {
            actions.add(action)
            resources.push([action, new Immutable.Map(parameters)])
          } else if (channel) {
            channels.add(channel)
          }
        }
      }
      return [new Map(resources), channels]
    }

    render() {
      return <WrappedComponent {...this.props} />
    }
  }

  WithSubscriptions.displayName = `WithSubscriptions(${getDisplayName(
    WrappedComponent
  )})`

  return WithSubscriptions
}

export const withSubscription = (action, calculateParameters) =>
  withSubscriptions(props => {
    const parameters = calculateParameters(props)
    if (parameters === null) return []
    return [{ action, parameters: parameters }]
  })*/

//export default withSubscription
