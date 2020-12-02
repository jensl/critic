import { Immutable, produce as immerProduce, enableMapSet } from "immer"
import { Reducer } from "redux"

import { Action } from "../actions"

enableMapSet()

const produce = <State>(
  fn: (draft: State, action: Action) => void,
  initial: Immutable<State>,
): Reducer<Immutable<State>, Action> => immerProduce(fn, initial)

export default produce
