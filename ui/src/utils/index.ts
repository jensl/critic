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

import React from "react"

import { useBranch } from "./BranchContext"
import { useChangeset } from "./ChangesetContext"
import Flag, { useFlag } from "./Flag"
import {
  id,
  all,
  any,
  count,
  sum,
  getProperty,
  map,
  sorted,
  sortedBy,
  setWith,
  setWithout,
} from "./Functions"
import Hash, { useHash } from "./Hash"
import { useRepository } from "./RepositoryContext"
import { useSubscription, useSubscriptionIf } from "./ResourceSubscriber"
import { useReview } from "./ReviewContext"
import { maybeParseInt } from "./Strings"
import Value, { useValue } from "./Value"
import UserSetting, { useUserSetting } from "./UserSetting"
import { useSignedInUser } from "./SessionContext"
import { State } from "../state"
import { extra, resource } from "../reducers"
import Review from "../resources/review"
import User from "../resources/user"
import { useSelector } from "../store"

export {
  Flag,
  Hash,
  id,
  all,
  any,
  count,
  sum,
  getProperty,
  map,
  maybeParseInt,
  useBranch,
  useChangeset,
  useFlag,
  useHash,
  useRepository,
  useReview,
  UserSetting,
  useSignedInUser,
  useSubscription,
  useSubscriptionIf,
  useUserSetting,
  useValue,
  Value,
  sorted,
  sortedBy,
  setWith,
  setWithout,
}

/*export const stopIf = (...checks) => WrappedComponent => props => {
  for (const check of checks) {
    if (check(props)) return null
  }
  return <WrappedComponent {...props} />
}
*/

/*
export const stopIf = predicate => branch(predicate, renderNothing)

export const stopUnlessHash = values =>
  compose(
    withHash,
    stopIf(({ hash, ...props }) => {
      const wanted = values(props)
      return Immutable.Seq(wanted).some(
        (value, key) =>
          !hash.has(key) ||
          (typeof value === "function"
            ? !value(hash.get(key))
            : value !== hash.get(key))
      )
    })
  )

export const stopUnlessDialog = dialogName =>
  compose(
    stopUnlessHash(props => ({ dialog: dialogName })),
    withProps(({ updateHash }) => ({
      closeDialog: () => updateHash({ dialog: null }),
    }))
  )

export const loaderIf = (...checks) => WrappedComponent => props => {
  for (const check of checks) {
    if (check(props)) return <div className="loader" />
  }
  return <WrappedComponent {...props} />
}

export const stopMouseEvents = {
  onMouseDown: event => event.stopPropagation(),
  onClick: event => {
    event.stopPropagation()
    event.preventDefault()
  },
}

export const omitProps = (...keys) => mapProps(props => omit(props, keys))

const defaultGetKey = <K, V>([key, _]: [K, V]) => key
const defaultGetValue = <K, V>([_, value]: [K, V]) => value
const defaultMapValue = <V>(value: V) => value
*/

export function* mapIter<T, U>(items: Iterable<T>, fn: (item: T) => U) {
  for (const item of items) yield fn(item)
}

export function makeMap<
  K_in,
  V_in,
  K_out = K_in,
  V_inter = V_in,
  V_out = V_inter
>(
  entries: Iterable<[K_in, V_in]>,
  {
    getKey = null,
    getValue = null,
    mapValue = null,
  }: {
    getKey?: ((entry: [K_in, V_in]) => K_out) | null
    getValue?: ((entry: [K_in, V_in]) => V_inter) | null
    mapValue?: ((value: V_inter) => V_out) | null
  } = {},
) {
  const usedGetKey =
    getKey || ((entry: [K_in, V_in]) => (entry[0] as unknown) as K_out)
  const usedGetValue =
    getValue || (([_, value]: [K_in, V_in]) => (value as unknown) as V_inter)
  const usedMapValue =
    mapValue || ((value: V_inter) => (value as unknown) as V_out)
  const transformEntry = (entry: [K_in, V_in]): [K_out, V_out] => [
    usedGetKey(entry),
    usedMapValue(usedGetValue(entry)),
  ]
  return new Map(mapIter(entries, transformEntry))
}

export const groupBy = <K, V>(items: Iterable<V>, getKey: (item: V) => K) => {
  const groups = new Map<K, V[]>()
  for (const item of items) {
    const key = getKey(item)
    let group = groups.get(key) || null
    if (group === null) groups.set(key, (group = []))
    group.push(item)
  }
  return groups.entries()
}

/*
export const withSystemSettings = settings =>
  compose(
    withSubscriptions(() =>
      Object.keys(settings).map(key => ({
        action: loadSystemSetting,
        parameters: { systemSettingID: settings[key] },
      }))
    ),
    connect(state => {
      const allSettings = state.resource.systemsettings
      const result = {}
      for (const key of Object.keys(settings))
        result[key] = allSettings.get(settings[key], {}).value
      return result
    }),
    stopIf(props => any(Object.keys(settings), key => props[key] === undefined))
  )
  */

export const signedInUser = (state: State) => {
  const session = state.resource.sessions.get("current")
  return typeof session?.user === "number"
    ? state.resource.users.byID.get(session.user)
    : null
}

export const isReviewOwner = (review: Review, user: User | null) =>
  user !== null && review.owners.has(user.id)

export const useDialog = (dialogID: string) => {
  const { hash, updateHash } = useHash()
  return {
    isOpen: hash.get("dialog") === dialogID,
    openDialog: () => updateHash({ dialog: dialogID }),
    closeDialog: () => updateHash({ dialog: null }),
  }
}

export const SidebarContext = React.createContext<{
  variant: "persistent" | "temporary"
  hideIfTemporary: () => void
}>({ variant: "persistent", hideIfTemporary: () => void 0 })

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
