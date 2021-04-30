import { Immutable, Draft, produce as immerProduce, enableMapSet } from "immer"
import { Reducer } from "redux"

import { Action } from "../actions"

enableMapSet()

const produce = <State>(
  fn: (draft: Draft<State>, action: Action) => void,
  initial: Immutable<State>,
): Reducer<Immutable<State>, Action> => immerProduce(fn, initial)

export default produce
