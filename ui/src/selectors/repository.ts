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

import Repository from "../resources/repository"
import { RepositoryID } from "../resources/types"
import { State } from "../state"

type RepositoryProp = { repository: Repository | null }
type RepositoryIDProp = { repositoryID: RepositoryID }
type GetRepositoryProps = RepositoryProp | RepositoryIDProp

const isRepositoryProp = (props: GetRepositoryProps): props is RepositoryProp =>
  "repository" in props

export const getRepository = (state: State, props: GetRepositoryProps) =>
  isRepositoryProp(props)
    ? props.repository
    : state.resource.repositories.byID.get(props.repositoryID)
