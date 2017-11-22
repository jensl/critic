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
import fetch from "isomorphic-fetch"

import { incrementCounter, decrementCounter } from "../actions/ui"
import { showToast } from "../actions/uiToast"
import { Dispatch } from "../state"
import {
  ExcludeFields,
  FetchJSONParams,
  FetchJSONResult,
  RequestParams,
  ExpectStatusCallback,
  HTTPMethod,
} from "./Fetch.types"
import { ResourceData } from "../types"

export const FETCH_IN_PROGRESS_COUNTER = "fetch-in-progress"

export class FetchException {
  name: string
  message: string
  status: number

  constructor(message: string, status: number) {
    this.message = message
    this.name = "FetchException"
    this.status = status
  }
}

const displayErrorMessage = (
  path: string,
  options: RequestInit,
  response: any
) => (dispatch: Dispatch) => {
  const message = (
    <div>
      <div className="toast_table">
        <b>Request: </b>
        <span className="monospace">{`${
          options.method || "GET"
        } /${path}`}</span>
        <b>Response: </b>
        <span className="monospace">
          {response.status} {response.statusText}
        </span>
      </div>
      <p>See the browser's error console for more details.</p>
    </div>
  )
  dispatch(
    showToast({
      type: "error",
      title: "API request failed",
      content: message,
      timeoutMS: 10000,
    })
  )
}

const defaultHeaders: Headers = new Headers({
  Accept: "application/vnd.api+json",
})

interface FetchTextParams {
  path: string
  params: RequestParams
  options?: RequestInit
}

export const fetchText = async ({
  path,
  params,
  options = {},
}: FetchTextParams) => {
  const useOptions: RequestInit = {
    credentials: "same-origin",
    ...options,
  }

  const query = Object.keys(params)
    .sort()
    .filter((key) => params[key] !== undefined)
    .map(
      (key) =>
        `${encodeURIComponent(key)}=${encodeURIComponent(String(params[key]))}`
    )
    .join("&")

  let url = "/" + path
  if (query) url += "?" + query

  return await fetch(url, useOptions)
}

export const mergeExcludeFields = (...args: ExcludeFields[]): ExcludeFields => {
  let intermediate = new Map<string, Set<string>>()
  for (const arg of args) {
    for (const [resourceName, fields] of Object.entries(arg)) {
      let perResource = intermediate.get(resourceName)
      if (!perResource)
        intermediate.set(resourceName, (perResource = new Set<string>()))
      for (const field of fields) perResource.add(field)
    }
  }
  let result: ExcludeFields = {}
  for (const [resourceName, perResource] of intermediate.entries())
    result[resourceName] = [...perResource]
  return result
}

interface Preloaded {
  [url: string]: ResourceData
}

declare global {
  interface Window {
    preloaded?: Preloaded
  }
}

export const fetchJSON = ({
  path,
  include,
  excludeFields = null,
  params = {},
  options = {},
  post = null,
  put = null,
  expectStatus = null,
  handleError = {},
}: FetchJSONParams) => async (dispatch: Dispatch): Promise<FetchJSONResult> => {
  const useParams: RequestParams = { output_format: "static" }

  for (const [name, value] of Object.entries(params))
    if (value !== undefined) useParams[name] = value

  if (include && include.length)
    useParams["include"] = [...include].sort().join(",")

  if (excludeFields !== null)
    Object.keys(excludeFields).forEach((resourceName: string) => {
      useParams[`fields[${resourceName}]`] = `-${excludeFields[resourceName]}`
    })

  var useExpectStatus: null | true | ExpectStatusCallback
  if (expectStatus instanceof Array)
    useExpectStatus = (status: number) => expectStatus.includes(status)
  else useExpectStatus = expectStatus

  var queryParams = Object.keys(useParams)
    .sort()
    .map(
      (key) =>
        `${encodeURIComponent(key)}=${encodeURIComponent(
          String(useParams[key])
        )}`
    )

  const components = path.split("/")
  const resourceName =
    components[components.length - (2 - (components.length % 2))]

  var url = "api/v1/" + path

  if (queryParams.length > 0) url += "?" + queryParams.join("&")

  if (window.preloaded && url in window.preloaded) {
    const preloadedResult = window.preloaded[url]
    delete window.preloaded[url]
    return { resourceName, status: 200, json: preloadedResult }
  }

  const useOptions: RequestInit = {
    credentials: "same-origin",
    headers: defaultHeaders,
    ...options,
  }

  if (post !== null) {
    useOptions.method = HTTPMethod.POST
    useOptions.body = JSON.stringify(post)
  } else if (put !== null) {
    useOptions.method = HTTPMethod.PUT
    useOptions.body = JSON.stringify(put)
  }

  if (useExpectStatus === null) {
    if (
      options.method === HTTPMethod.DELETE &&
      useParams.output_format !== "static"
    ) {
      useExpectStatus = (status) => status === 204
    } else {
      useExpectStatus = (status) => status === 200
    }
  }

  dispatch(incrementCounter(FETCH_IN_PROGRESS_COUNTER))

  console.log("fetch", { url, useOptions })

  try {
    const response = await fetch("/" + url, useOptions)
    const { status } = response

    if (useExpectStatus !== true && !useExpectStatus(status)) {
      if (status === 500) console.error(await response.text())

      if ([400, 404].includes(status)) {
        const { error } = await response.json()
        if (error.code && handleError !== null && handleError[error.code]) {
          handleError[error.code](error)
        } else {
          dispatch(
            showToast({
              type: "error",
              title: error.title,
              content: error.message,
              timeoutMS: 10000,
            })
          )
        }
      } else dispatch(displayErrorMessage(path, useOptions, response))

      throw new FetchException("Unexpected status returned", status)
    }

    if (status === 204) return { resourceName, status, json: {} }

    const json = await response.json()

    return { resourceName, status, json }
  } finally {
    dispatch(decrementCounter(FETCH_IN_PROGRESS_COUNTER))
  }
}
