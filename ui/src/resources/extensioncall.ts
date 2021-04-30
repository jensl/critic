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

import { immerable } from "immer"

import { primaryMap } from "../reducers/resource"
import {
  UserID,
  ExtensionVersionID,
  AccessTokenID,
  ExtensionCallID,
} from "./types"

export type EndpointRequest = {
  method: string
  path: string
  query: { [key: string]: string }
}

export type EndpointCallRequest = {
  type: "endpoint"
  name: string
  request: EndpointRequest
}

export type SubscriptionPayload = {
  __type__: string
  [key: string]: any
}

export type SubscriptionMessage = {
  channel: string
  payload: SubscriptionPayload
}

export type SubscriptionCallRequest = {
  type: "subscription"
  message: SubscriptionMessage
}

export type CallRequest = EndpointCallRequest | SubscriptionCallRequest

type ExtensionCallData = {
  id: ExtensionCallID
  version: ExtensionVersionID
  user: UserID | null
  accesstoken: AccessTokenID | null
  request: CallRequest
  response: any
  successful: boolean | null
  request_time: number
  response_time: number | null
}

type ExtensionCallProps = {
  id: ExtensionCallID
  version: ExtensionVersionID
  user: UserID | null
  accesstoken: AccessTokenID | null
  request: CallRequest
  response: any
  successful: boolean | null
  request_time: number
  response_time: number | null
}

class ExtensionCall {
  [immerable] = true

  constructor(
    readonly id: ExtensionCallID,
    readonly version: ExtensionVersionID,
    readonly user: UserID | null,
    readonly accesstoken: AccessTokenID | null,
    readonly request: CallRequest,
    readonly response: any,
    readonly successful: boolean | null,
    readonly requestTime: number,
    readonly responseTime: number | null,
  ) {}

  static new(props: ExtensionCallProps) {
    return new ExtensionCall(
      props.id,
      props.version,
      props.user,
      props.accesstoken,
      props.request,
      props.response,
      props.successful,
      props.request_time,
      props.response_time,
    )
  }

  static reducer = primaryMap<ExtensionCall, ExtensionCallID>("extensioncalls")

  get props(): ExtensionCallProps {
    return {
      ...this,
      request_time: this.requestTime,
      response_time: this.responseTime,
    }
  }
}

export default ExtensionCall
