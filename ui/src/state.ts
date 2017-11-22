import { ThunkDispatch } from "redux-thunk"

import reducer from "./reducers"
import { Action } from "./actions"

export type State = ReturnType<typeof reducer>
export type Dispatch = ThunkDispatch<State, null, Action>
export type GetState = () => State

export type Thunk<T> = (dispatch: Dispatch, getState: GetState) => T
export type AsyncThunk<T> = (
  dispatch: Dispatch,
  getState: GetState
) => Promise<T>

export type Reducer<S> = (state: S, action: Action) => S
