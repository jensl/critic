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
import { Route, Switch } from "react-router"
import { Router } from "react-router-dom"

import App from "./components/App"
import About from "./components/About"
import NotFound from "./components/Application.NotFound"
import Review from "./components/Review"
import ReviewList from "./components/ReviewList"
import Changeset from "./components/Changeset"
import CommentChain from "./components/CommentChain"

const Routes = (props) => (
  <Router {...props}>
    <Switch>
      <Route name="home" exact path="/" component={ReviewList} />
      <Route path="/r/:id" component={Review} />
      <Route path="/comment/:id" component={CommentChain} />
      <Route
        path="/changeset/by-sha1/:from/:to/:repository"
        component={Changeset}
      />
      <Route path="/changeset/:id/:repository" component={Changeset} />
      <Route path="*" component={NotFound} />
    </Switch>
  </Router>
)

export default Routes
