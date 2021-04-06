import { defer } from "lodash"
import React, { useContext, useState } from "react"
import { assertNotNull } from "../debug"
import { Thunk } from "../state"
import { useDispatch } from "../store"
import { soon } from "./Functions"

class MouseState {
  isDown: boolean = false
  absoluteX: number = 0
  absoluteY: number = 0
  downAbsoluteX: number = 0
  downAbsoluteY: number = 0
}

const MouseContext = React.createContext<
  [MouseState, React.Dispatch<React.SetStateAction<MouseState>>] | [null, null]
>([null, null])

export type MouseMonitor = (state: MouseState) => Thunk<MouseState | null>

export const useMouseTracker = () => {
  const dispatch = useDispatch()
  const [state, setState] = useContext(MouseContext)

  assertNotNull(state)
  assertNotNull(setState)

  return (event: MouseEvent, monitor: MouseMonitor) => {
    // Do nothing unless it's the primary mouse button being depressed.
    if (event.button !== 0) return

    const callMonitor = (updates: Partial<MouseState>) =>
      setState((currentState) => {
        const newState = { ...currentState, ...updates }
        soon(() => dispatch(monitor(newState)))
        return newState
      })

    const document = (event.target as Node).ownerDocument!

    const position = (event: MouseEvent) => ({
      absoluteX: event.pageX,
      absoluteY: event.pageY,
    })

    const onMouseMove = (event: MouseEvent) => {
      if (event.button !== 0) return
      console.log("onMouseMove")
      callMonitor(position(event))
    }

    const onMouseUp = (event: MouseEvent) => {
      if (event.button !== 0) return
      document.removeEventListener("mouseup", onMouseUp, { capture: true })
      document.removeEventListener("mousemove", onMouseMove, { capture: true })
      console.log("onMouseUp")
      callMonitor({ ...position(event), isDown: false })
    }

    document.addEventListener("mouseup", onMouseUp, { capture: true })
    document.addEventListener("mousemove", onMouseMove, { capture: true })

    console.log("initial")
    callMonitor({
      isDown: true,
      absoluteX: event.pageX,
      absoluteY: event.pageY,
      downAbsoluteX: event.pageX,
      downAbsoluteY: event.pageY,
    })
  }
}

export const useMousePosition = () => {
  const [state] = useContext(MouseContext)
  assertNotNull(state)
  return state
}

const MouseTracker: React.FunctionComponent = ({ children }) => (
  <MouseContext.Provider value={useState(new MouseState())}>
    {children}
  </MouseContext.Provider>
)

export default MouseTracker
