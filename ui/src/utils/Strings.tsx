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

export const getShortened = (string: string) => {
  var text = ""
  const split = string.split("\n")
  const lineLimit = 80
  if (split[0].length > lineLimit) {
    text = split[0].split(" ").reduce((acc, word) => {
      if (acc.length + word.length + 1 < lineLimit) {
        return acc + " " + word
      } else {
        return acc
      }
    })
  } else {
    text = split[0]
  }
  if (split.length > 1 || split[0].length >= lineLimit) {
    text += " ..."
  }
  return text
}

export const maybePlural = (count: number, string: string, suffix = "s") =>
  `${string}${count !== 1 ? suffix : ""}`

export const countWithUnit = (count: number, string: string, suffix = "s") =>
  `${count} ${maybePlural(count, string, suffix)}`

export const humanReadableSize = (size: number) => {
  if (size < 1024) {
    return `${size} B`
  }
  if ((size /= 1024) < 1024) {
    return `${size.toFixed(2)} kB`
  }
  if ((size /= 1024) < 1024) {
    return `${size.toFixed(2)} MB`
  }
  if ((size /= 1024) < 1024) {
    return `${size.toFixed(2)} GB`
  }
  // Let's hope terabyte resolution is enough. :-)
  return `${(size /= 1024).toFixed(2)} TB`
}

// eslint-disable-next-line no-useless-escape
const SPLIT_PATH = /^(.+\/)([^\/]+)$/

export const splitPath = (path: string) => {
  const match = SPLIT_PATH.exec(path)
  if (match !== null) {
    return match.slice(1)
  }
  return [null, path]
}

export const joinPaths = (...components: string[]) => {
  var result = ""
  for (const component of components) {
    if (component) {
      if (result && !result.endsWith("/")) {
        result += "/"
      }
      result += component
    }
  }
  return result
}

export const longestCommonPathPrefix = (paths: Iterable<string>) => {
  let longestPrefix: string[] | null = null
  for (const path of paths) {
    if (!path.includes("/")) return null
    const prefix = path.split("/")
    prefix.pop()
    if (longestPrefix === null) longestPrefix = prefix
    else {
      const limit = Math.max(prefix.length, longestPrefix.length)
      let index = 0
      while (index < limit)
        if (prefix[index] !== longestPrefix[index]) break
        else ++index
      if (index === 0) return null
      longestPrefix.splice(index)
    }
  }
  if (!longestPrefix) return null
  return longestPrefix.join("/") + "/"
}

export const maybeParseInt = (value: string) => {
  const valueAsInt = parseInt(value, 10)
  if (String(valueAsInt) === value) return valueAsInt
  return value
}

export const textFromChildren = (children: React.ReactNode) =>
  React.Children.map(children, (child: unknown) =>
    typeof child === "string" ? child : "",
  )?.join("") ?? ""
