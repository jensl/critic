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
import isArray from "lodash/isArray"
import isObject from "lodash/isObject"
import isEqual from "lodash/isEqual"
import isPlainObject from "lodash/isPlainObject"
import map from "lodash/map"
import values from "lodash/values"
import flatten from "lodash/flatten"
import { immerable } from "immer"

import { useDispatch, useSelector } from "../store"
import Token from "./Token"
import { AsyncThunk, Dispatch, Thunk } from "../state"
import { filterInPlace, soon } from "./Functions"
import { assertNotNull } from "../debug"
import { ShortcutScope } from "./KeyboardShortcuts"
import { extra, resource } from "../reducers"

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
      console.debug("New subscription", {
        fetch: fnName(fetch),
        args,
        subscriptions,
      })
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
  if (isObject(arg) && immerable in arg && "id" in arg)
    [(arg as { id: any })["id"]]
  return [arg]
}

const fnName = (fn: any) => fn.name ?? String(fn)

export function useSubscription<T extends any[]>(
  fetch: FetchCallback<T>,
  args: T,
  deps: any[] = [],
) {
  useSubscriptionIf(true, fetch, args, deps)
}

export const useSubscriptionIf = <T extends any[]>(
  predicate: boolean,
  fetch: FetchCallback<T>,
  args: T,
  deps: any[] = [],
) => {
  const subscriptions = useContext(ResourceSubscriptionsContext)
  assertNotNull(subscriptions)
  useEffect(() => {
    if (!predicate) return
    return subscriptions.addSubscriber(fetch, args)
  }, [predicate, ...deps, ...dependencies(args)]) // eslint-disable-line react-hooks/exhaustive-deps
}

const ResourceSubscriptions: React.FunctionComponent<{
  className?: string
}> = ({ children, ...props }) => {
  const dispatch = useDispatch()
  const subscriptions = new ResourceSubscriptionsState(dispatch)
  return (
    <ResourceSubscriptionsContext.Provider value={subscriptions}>
      <ShortcutScope
        name="ResourceSubscriptions"
        handler={{
          R: () => subscriptions.reload(),
        }}
        componentProps={props}
      >
        {children}
      </ShortcutScope>
    </ResourceSubscriptionsContext.Provider>
  )
}

type R = ReturnType<typeof resource>

export function useResource<K extends keyof R>(name: K): R[K]
export function useResource<K extends keyof R, V>(
  name: K,
  map: (value: R[K]) => V,
): V

export function useResource<K extends keyof R, V>(
  name: K,
  map?: (value: R[K]) => V,
): R[K] | V {
  const value = useSelector((state) => state.resource[name])
  return map ? map(value) : value
}

type E = ReturnType<typeof extra>

export function useResourceExtra<K extends keyof E>(name: K): E[K]
export function useResourceExtra<K extends keyof E, V>(
  name: K,
  map: (value: E[K]) => V,
): V

export function useResourceExtra<K extends keyof E, V>(
  name: K,
  map?: (value: E[K]) => V,
): E[K] | V {
  const value = useSelector((state) => state.resource.extra[name])
  return map ? map(value) : value
}

export default ResourceSubscriptions
