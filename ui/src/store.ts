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

/* eslint-disable import/first */

import { createStore, applyMiddleware, Middleware } from "redux"
import thunkMiddleware from "redux-thunk"
import { createLogger } from "redux-logger"
//import { persistStore, autoRehydrate } from "redux-persist"
//import { createBlacklistFilter } from "redux-persist-transform-filter"
//import immutableTransform from "redux-persist-transform-immutable"
import {
  useDispatch as _useDispatch,
  useSelector as _useSelector,
} from "react-redux"

import Reducer from "./reducers"
//import { recordTypes as resourceRecordTypes } from "./resources"
//import { recordTypes as reducerRecordTypes } from "./reducers"
import { START } from "./actions"
import { Dispatch, State } from "./state"

const middleware: Middleware[] = [thunkMiddleware]

if (process.env.NODE_ENV === "development") middleware.push(createLogger())

const enhancer = applyMiddleware(...middleware)

const store = createStore(Reducer, undefined, enhancer)

/*
const resourceFilter = createBlacklistFilter("resource", [
    // Don't persist filediffs, since it will potentially be a lot of data.
    "filediffs",

    // Don't persist the current session. We expect the backend to preload
    // it anyway, and having stale session information won't be useful.
    "sessions",
])

persistStore(
    store,
    {
        blacklist: [
            // Don't persist any UI state. TODO: We might want to persist some,
            // so might be better with a proper filter with a whitelist.
            "ui"
        ],
        transforms: [
            resourceFilter,
            immutableTransform({
                records: [].concat(resourceRecordTypes, reducerRecordTypes),
                whitelist: ["resource"]
            })
        ]
    },
    () => store.dispatch(start())
)
*/

setTimeout(() => store.dispatch({ type: START }), 0)

export const useDispatch = () => _useDispatch<Dispatch>()
export const useSelector = <Selected>(selector: (state: State) => Selected) =>
  _useSelector(selector)

export default store
