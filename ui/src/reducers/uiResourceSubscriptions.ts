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
import isEqual from "lodash/isEqual"

import {
  Action,
  ADD_SUBSCRIPTION,
  ADD_SUBSCRIBER,
  REMOVE_SUBSCRIBER,
  CHECK_SUBSCRIPTION,
  SubscribedAction,
} from "../actions"
import { assertNull, assertNotNull } from "../debug"

import Token from "../utils/Token"

export class Subscription extends Immutable.Record<{
  action: SubscribedAction
  args: any[]
  tokens: Immutable.Set<Token>
}>(
  {
    action: () => null,
    args: [],
    tokens: Immutable.Set<Token>(),
  },
  "Subscription"
) {}

export const findSubscriptionByArgs = (
  state: Immutable.Map<SubscribedAction, Immutable.List<Subscription>>,
  action: (...args: any[]) => any,
  args: any[]
): [number, Subscription | null] => {
  const subscriptions = state.get(action)
  if (!subscriptions) return [-1, null]
  const index = subscriptions.findIndex(
    (subscription) =>
      subscription.action === action && isEqual(subscription.args, args)
  )
  return [index, index === -1 ? null : subscriptions.get(index, null)]
}

export const findSubscriptionByToken = (
  state: Immutable.Map<SubscribedAction, Immutable.List<Subscription>>,
  action: (...args: any[]) => any,
  token: Token
): [number, Subscription | null] => {
  const subscriptions = state.get(action)
  if (!subscriptions) return [-1, null]
  const index = subscriptions.findIndex(
    (subscription) =>
      subscription.action === action && subscription.tokens.has(token)
  )
  return [index, index === -1 ? null : subscriptions.get(index, null)]
}

const fnName = (fn: any) =>
  String(fn).replace(/^function\s+(\w+)\([\s\S]*$/, "$1")

export const resourceSubscriptions = (
  state = Immutable.Map<SubscribedAction, Immutable.List<Subscription>>(),
  action: Action
): Immutable.Map<SubscribedAction, Immutable.List<Subscription>> => {
  switch (action.type) {
    case ADD_SUBSCRIPTION:
    case ADD_SUBSCRIBER:
    case CHECK_SUBSCRIPTION: {
      const [index, subscription] = findSubscriptionByArgs(
        state,
        action.action,
        action.args
      )

      switch (action.type) {
        case ADD_SUBSCRIPTION:
          assertNull(subscription)
          let subscriptions = state.get(action.action)
          if (!subscriptions)
            state = state.set(
              action.action,
              (subscriptions = Immutable.List<Subscription>())
            )
          return state.set(
            action.action,
            subscriptions.push(new Subscription({ ...action }))
          )

        case ADD_SUBSCRIBER:
          assertNotNull(subscription)
          return state.setIn(
            [action.action, index, "tokens"],
            subscription!.tokens.add(action.token)
          )

        case CHECK_SUBSCRIPTION:
        default:
          console.debug("Checking subscription", {
            action: fnName(action.action),
            args: action.args,
          })
          if (subscription && subscription.tokens.size === 0) {
            console.debug("Deleting subscription!")
            return state.deleteIn([action.action, index])
          }
          return state
      }
    }

    case REMOVE_SUBSCRIBER:
      const [index, subscription] = findSubscriptionByToken(
        state,
        action.action,
        action.token
      )
      assertNotNull(subscription)
      return state.setIn(
        [action.action, index, "tokens"],
        subscription!.tokens.delete(action.token)
      )

    default:
      return state
  }
}
