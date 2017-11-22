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

import { SET_MOUSE_IS_DOWN, SET_MOUSE_POSITION, Action } from "."
import { Dispatch, GetState } from "../state"

export const setMouseIsDown = (value: boolean): Action => ({
  type: SET_MOUSE_IS_DOWN,
  value,
})

export const setMousePosition = (x: number, y: number): Action => ({
  type: SET_MOUSE_POSITION,
  x,
  y,
})

type Monitor = (x: number, y: number, isDown: boolean) => any

export const onMouseDown = (event: MouseEvent, monitor: Monitor) => {
  // Do nothing unless it's the primary mouse button being depressed.
  if (event.button !== 0) return () => null

  var isDown = true
  var handleMove: ((x: number, y: number) => void) | null = null
  var handleUp: ((x: number, y: number) => void) | null = null
  const document = (event.target as Node).ownerDocument!

  const onMouseMove = (event: MouseEvent) => {
    if (handleMove !== null) handleMove(event.pageX, event.pageY)
  }

  const onMouseUp = (event: MouseEvent) => {
    isDown = false
    document.removeEventListener("mouseup", onMouseUp, true)
    document.removeEventListener("mousemove", onMouseMove, true)
    if (handleUp !== null) handleUp(event.pageX, event.pageY)
  }

  document.addEventListener("mouseup", onMouseUp, true)
  document.addEventListener("mousemove", onMouseMove, true)

  return (dispatch: Dispatch, getState: GetState) => {
    const callMonitor = (x: number, y: number, isDown: boolean) =>
      dispatch(monitor(x, y, isDown))

    dispatch(setMousePosition(event.pageX, event.pageY))
    dispatch(setMouseIsDown(true))

    callMonitor(event.pageX, event.pageY, true)

    if (isDown) {
      handleMove = (x: number, y: number) => {
        dispatch(setMousePosition(x, y))
        callMonitor(x, y, true)
      }

      handleUp = (x: number, y: number) => {
        dispatch(setMousePosition(x, y))
        dispatch(setMouseIsDown(false))
        callMonitor(x, y, false)
      }
    } else {
      dispatch(setMouseIsDown(false))

      callMonitor(event.pageX, event.pageY, false)
    }
  }
}
