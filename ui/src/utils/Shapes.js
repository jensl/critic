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

import PropTypes from "prop-types"

export const Commit = PropTypes.shape({
  id: PropTypes.number.isRequired,
  sha1: PropTypes.string.isRequired,
})

export const Review = PropTypes.shape({
  id: PropTypes.number.isRequired,
})

export const Comment = PropTypes.shape({
  id: PropTypes.number.isRequired,
  type: PropTypes.oneOf(["issue", "note"]),
})

export const Repository = PropTypes.shape({
  id: PropTypes.number.isRequired,
  name: PropTypes.string.isRequired,
})

export default { Commit, Review, Comment, Repository }
