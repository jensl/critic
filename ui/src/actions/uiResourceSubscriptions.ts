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

import defer from "lodash/defer"

import { Dispatch, GetState } from "../state"
import Token from "../utils/Token"
import {
  SubscribedAction,
  ADD_SUBSCRIPTION,
  ADD_SUBSCRIBER,
  REMOVE_SUBSCRIBER,
  CHECK_SUBSCRIPTION,
  Action,
} from "."
import {
  findSubscriptionByArgs,
  findSubscriptionByToken,
  Subscription,
} from "../reducers/uiResourceSubscriptions"

const addSubscription = (action: SubscribedAction, args: any[]): Action => ({
  type: ADD_SUBSCRIPTION,
  action,
  args,
})

const addSubscriber = (
  action: SubscribedAction,
  args: any[],
  token: Token
): Action => ({
  type: ADD_SUBSCRIBER,
  action,
  args,
  token,
})

const fnName = (fn: any) =>
  String(fn).replace(/^function\s+(\w+)\([\s\S]*$/, "$1")

export const registerSubscriber = (action: SubscribedAction, args: any[]) => (
  dispatch: Dispatch,
  getState: GetState
) => {
  const token = Token.create()
  const [, subscription] = findSubscriptionByArgs(
    getState().ui.resourceSubscriptions,
    action,
    args
  )
  if (!subscription) {
    console.debug("New subscription", { action: fnName(action), args })
    dispatch(addSubscription(action, args))
    dispatch(action(...args))
  }
  console.debug("New subscriber", { action: fnName(action), args, token })
  dispatch(addSubscriber(action, args, token))
  return token
}

const removeSubscriber = (action: SubscribedAction, token: Token): Action => ({
  type: REMOVE_SUBSCRIBER,
  action,
  token,
})

const checkSubscription = (action: SubscribedAction, args: any[]): Action => ({
  type: CHECK_SUBSCRIPTION,
  action,
  args,
})

export const unregisterSubscriber = (
  action: SubscribedAction,
  token: Token
) => (dispatch: Dispatch, getState: GetState) => {
  const [, subscription] = findSubscriptionByToken(
    getState().ui.resourceSubscriptions,
    action,
    token
  )
  if (subscription) {
    console.debug("Unregister subscriber", {
      action: fnName(action),
      args: subscription.args,
      count: subscription.tokens.size,
      token,
    })
    dispatch(removeSubscriber(action, token))
    defer(dispatch, checkSubscription(action, subscription.args))
  }
}

export const reloadSubscription = (subscription: Subscription) =>
  subscription.action(...subscription.args)
