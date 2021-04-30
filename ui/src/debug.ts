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

export class DebugError extends Error {}

export const IS_DEVELOPMENT = process.env.NODE_ENV === "development"

export const assertNotReached = IS_DEVELOPMENT
  ? (message = "This line should not be reachable!"): never => {
      throw new DebugError(message)
    }
  : () => {}

export function assertTrue(
  actual: boolean,
  message: string = "Expected true",
): asserts actual {
  if (!actual) {
    console.error("assertTrue failed", { actual })
    throw new DebugError(`assertTrue(): ${message}`)
  }
}

export const assertFalse = IS_DEVELOPMENT
  ? (actual: boolean, message = "Expected false") => {
      if (actual) {
        console.error("assertFalse failed", { actual })
        throw new DebugError(`assertFalse(): ${message}`)
      }
    }
  : () => {}

export const assertEqual = IS_DEVELOPMENT
  ? <T>(a: T, b: T, message = "Expected equal") => {
      if (!(a === b)) {
        console.error("assertEqual failed", { a, b })
        throw new DebugError(`asssertEqual(): ${message}`)
      }
    }
  : () => {}

export const assertNotEqual = IS_DEVELOPMENT
  ? <T>(a: T, b: T, message = "Expected not equal") => {
      if (!(a !== b)) {
        console.error("assertNotEqual failed", { a, b })
        throw new DebugError(`asssertNotEqual(): ${message}`)
      }
    }
  : () => {}

export function assertString(
  actual: unknown,
  message = "Expected string",
): asserts actual is string {
  if (typeof actual !== "string") {
    console.error("assertString failed", { actual })
    throw new DebugError(`asssertString(): ${message}`)
  }
}

export function assertNumber(
  actual: unknown,
  message = "Expected number",
): asserts actual is number {
  if (typeof actual !== "number") {
    console.error("assertNumber failed", { actual, message })
    throw new DebugError(`asssertNumber(): ${message}`)
  }
}

export const assertNull = IS_DEVELOPMENT
  ? <T extends {}>(actual: T | null, message = "Expected null") => {
      if (actual !== null) {
        console.error("assertFalse failed", { actual })
        throw new DebugError(`assertFalse(): ${message}`)
      }
    }
  : () => {}

export function assertNotNull<T>(
  actual: T,
  message: string = "Expected not null",
): asserts actual is NonNullable<T> {
  if (actual === null || actual === undefined) {
    console.error("assertFalse failed", { actual, message })
    throw new DebugError(`assertFalse(): ${message}`)
  }
}

export const assertInstanceOf = IS_DEVELOPMENT
  ? (actual: any, expectedClass: any, message = "Expected instance") => {
      if (!(actual instanceof expectedClass)) {
        console.error("assertInstanceOf failed", { actual, expectedClass })
        throw new DebugError(`assertTrue(): ${message}`)
      }
    }
  : () => {}

type NonArray<T> = T extends any[] ? never : T extends object ? T : never

export function assertIsObject<T>(
  actual: T,
  message = "Expected object",
): asserts actual is NonArray<T> {
  if (!actual || typeof actual !== "object" || Array.isArray(actual)) {
    console.error("assertIsObject failed", { actual })
    throw new DebugError(`assertIsObject(): ${message}`)
  }
}

export const nullBecause = (reason: string) => {
  console.log("RepositoryDiff returning null: ", { reason })
  return null
}
