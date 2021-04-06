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

// import isEqual from "lodash/isEqual"

// import produce from "./immer"
// import {
//   Action,
//   ADD_SUBSCRIPTION,
//   ADD_SUBSCRIBER,
//   REMOVE_SUBSCRIBER,
//   CHECK_SUBSCRIPTION,
//   SubscribedAction,
// } from "../actions"
// import { assertNull, assertNotNull } from "../debug"

// import Token from "../utils/Token"

// type Subscription = {
//   action: SubscribedAction
//   args: readonly any[]
//   tokens: Set<Token>
// }

// type State = Map<SubscribedAction, Subscription[]>

// type FindSubscriptionResult = {
//   subscriptions: Subscription[] | null
//   subscription: Subscription | null
//   index: number | null
// }

// const findSubscription = (
//   state: State,
//   action: SubscribedAction,
//   predicate: (subscription: Subscription) => boolean,
//   createIfMissing: boolean = false,
// ): FindSubscriptionResult => {
//   let subscriptions = state.get(action) ?? null
//   if (!subscriptions) {
//     if (createIfMissing) state.set(action, (subscriptions = []))
//     return { subscriptions, subscription: null, index: null }
//   }
//   const indexOrNull = (index: number) => (index >= 0 ? index : null)
//   const index = indexOrNull(subscriptions.findIndex(predicate))
//   const subscription = index !== null ? subscriptions[index] : null
//   return { subscriptions, subscription, index }
// }

// export const findSubscriptionByArgs = (
//   state: State,
//   action: SubscribedAction,
//   args: any[],
//   createIfMissing: boolean = false,
// ): FindSubscriptionResult =>
//   findSubscription(
//     state,
//     action,
//     (subscription) => isEqual(subscription.args, args),
//     createIfMissing,
//   )

// export const findSubscriptionByToken = (
//   state: State,
//   action: SubscribedAction,
//   token: Token,
// ): FindSubscriptionResult =>
//   findSubscription(state, action, (subscription) =>
//     subscription.tokens.has(token),
//   )

// const fnName = (fn: any) =>
//   String(fn).replace(/^function\s+(\w+)\([\s\S]*$/, "$1")

// export const resourceSubscriptions = produce(
//   (draft: State, dispatchedAction: Action) => {
//     switch (dispatchedAction.type) {
//       case ADD_SUBSCRIPTION:
//       case ADD_SUBSCRIBER:
//       case CHECK_SUBSCRIPTION:
//         {
//           const { action, args } = dispatchedAction
//           const { subscriptions, subscription, index } = findSubscriptionByArgs(
//             draft,
//             action,
//             args,
//             dispatchedAction.type === ADD_SUBSCRIPTION,
//           )

//           switch (dispatchedAction.type) {
//             case ADD_SUBSCRIPTION:
//               assertNotNull(subscriptions)
//               assertNull(subscription)
//               subscriptions.push({ action, args, tokens: new Set() })
//               break

//             case ADD_SUBSCRIBER:
//               assertNotNull(subscription)
//               subscription.tokens.add(dispatchedAction.token)
//               break

//             case CHECK_SUBSCRIPTION:
//               console.debug("Checking subscription", {
//                 action: fnName(action),
//                 args,
//               })
//               if (subscription?.tokens.size === 0) {
//                 assertNotNull(subscriptions)
//                 assertNotNull(index)
//                 console.debug("Deleting subscription!")
//                 subscriptions.splice(index, 1)
//               }
//               return draft
//           }
//         }
//         break

//       case REMOVE_SUBSCRIBER:
//         {
//           const { action, token } = dispatchedAction
//           const { subscription } = findSubscriptionByToken(draft, action, token)
//           assertNotNull(subscription)
//           subscription.tokens.delete(token)
//         }
//         break
//     }
//   },
//   new Map(),
// )

export {}
