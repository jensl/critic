/*
 * Copyright 2019 the Critic contributors, Opera Software ASA
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

import { JSONData, ResourceData } from "../types"

export type RequestParams = {
  [name: string]: number | string | undefined
}

export interface ExpectStatusCallback {
  (status: number): boolean
}

export type HTTPMethod = "GET" | "POST" | "PUT" | "DELETE"

export interface Options {
  credentials?: "include" | "same-origin" | "omit" | undefined
  headers?: { [name: string]: string }
  method?: HTTPMethod
  body?: string
}

export interface ExcludeFields {
  [resource: string]: string[]
}

export type HandleError = { [code: string]: (error: any) => boolean | void }

export interface FetchJSONParams {
  path: string
  include?: string[]
  excludeFields?: null | ExcludeFields
  params?: RequestParams
  options?: RequestInit
  post?: JSONData
  put?: JSONData
  expectStatus?: null | true | number[] | ExpectStatusCallback
  handleError?: null | HandleError
}

export interface FetchJSONResult {
  resourceName: string
  status: number
  json: ResourceData
}
