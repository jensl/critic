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

import { immerable } from "immer"

import { ResourceData } from "../types"
import { primaryMap } from "../reducers/resource"
import {
  CommentID,
  ReviewID,
  UserID,
  CommitID,
  ReplyID,
  FileID,
  ChangesetID,
  CommentType,
  IssueState,
  CommentLocationType,
} from "./types"

export type LineIDs = readonly string[]

type CommentData = {
  id: CommentID
  type: CommentType
  is_draft: boolean
  state: IssueState
  review: ReviewID
  author: UserID
  location: LocationData | null
  translated_location: LocationData | null
  resolved_by: UserID | null
  addressed_by: CommitID | null
  timestamp: number
  text: string
  replies: ReplyID[]
  draft_changes: DraftChangesData | null
}

type CommentProps = {
  id: CommentID
  type: CommentType
  is_draft: boolean
  state: IssueState
  review: ReviewID
  author: UserID
  location: Location | null
  translated_location: Location | null
  resolved_by: UserID | null
  addressed_by: CommitID | null
  timestamp: number
  text: string
  replies: readonly ReplyID[]
  draft_changes: DraftChanges | null
}

class Comment {
  [immerable] = true

  constructor(
    readonly id: CommentID,
    readonly type: CommentType,
    readonly isDraft: boolean,
    readonly state: IssueState,
    readonly review: ReviewID,
    readonly author: UserID,
    readonly location: Location | null,
    readonly translatedLocation: Location | null,
    readonly resolvedBy: UserID | null,
    readonly addressedBy: CommitID | null,
    readonly timestamp: number,
    readonly text: string,
    readonly replies: readonly ReplyID[],
    readonly draftChanges: DraftChanges | null,
  ) {}

  static new(props: CommentProps) {
    console.warn("Comment.new", { props })
    return new Comment(
      props.id,
      props.type,
      props.is_draft,
      props.state,
      props.review,
      props.author,
      props.location,
      props.translated_location,
      props.resolved_by,
      props.addressed_by,
      props.timestamp,
      props.text,
      props.replies,
      props.draft_changes,
    )
  }

  static prepare(value: CommentData): CommentProps {
    const prepared = {
      ...value,
      location: Location.make(value.location),
      translated_location: Location.make(value.translated_location),
      draft_changes: DraftChanges.make(value.draft_changes),
    }
    console.warn("Comment.prepare", { value, prepared })
    return prepared
  }

  static reducer = primaryMap<Comment, CommentID>("comments")

  get lineIDs(): LineIDs | null {
    if (!this.location || this.location.type !== "file-version") return null
    const { file, side, firstLine, lastLine } = this.location
    return Array.from(
      (function* () {
        for (let offset = firstLine; offset <= lastLine; ++offset) {
          yield `${file}:${side}:${offset}`
        }
      })(),
    )
  }

  get effectiveType() {
    return this.draftChanges?.newType || this.type
  }

  get effectiveState() {
    return this.draftChanges?.newState || this.state
  }

  get props(): CommentProps {
    return {
      ...this,
      is_draft: this.isDraft,
      translated_location: this.translatedLocation,
      resolved_by: this.resolvedBy,
      addressed_by: this.addressedBy,
      draft_changes: this.draftChanges,
    }
  }
}

type LocationData = {
  type: CommentLocationType
  first_line: number
  last_line: number
  file: null | FileID
  changeset: null | ChangesetID
  commit: null | CommitID
  side: null | "old" | "new"
}

type LocationProps = LocationData

export class Location {
  [immerable] = true

  constructor(
    readonly type: CommentLocationType,
    readonly firstLine: number,
    readonly lastLine: number,
    readonly file: FileID | null,
    readonly changeset: ChangesetID | null,
    readonly commit: CommitID | null,
    readonly side: "old" | "new" | null,
  ) {}

  static new(props: LocationProps) {
    return new Location(
      props.type,
      props.first_line,
      props.last_line,
      props.file,
      props.changeset,
      props.commit,
      props.side,
    )
  }

  static make(value: LocationData | null) {
    return value && Location.new(value)
  }

  get props(): LocationProps {
    return { ...this, first_line: this.firstLine, last_line: this.lastLine }
  }
}

type DraftChangesData = {
  author: UserID
  is_draft: boolean
  reply: ReplyID | null
  new_type: CommentType | null
  new_state: IssueState | null
  new_location: LocationData | null
}

type DraftChangesProps = {
  author: UserID
  is_draft: boolean
  reply: ReplyID | null
  new_type: CommentType | null
  new_state: IssueState | null
  new_location: Location | null
}

class DraftChanges {
  [immerable] = true

  constructor(
    readonly author: UserID,
    readonly isDraft: boolean,
    readonly reply: ReplyID | null,
    readonly newType: CommentType | null,
    readonly newState: IssueState | null,
    readonly newLocation: Location | null,
  ) {}

  static new(props: DraftChangesProps) {
    return new DraftChanges(
      props.author,
      props.is_draft,
      props.reply,
      props.new_type,
      props.new_state,
      props.new_location,
    )
  }

  static make(value: DraftChangesData | null) {
    return (
      value &&
      DraftChanges.new({
        ...value,
        new_location: Location.make(value.new_location),
      })
    )
  }

  get props(): DraftChangesProps {
    return {
      ...this,
      is_draft: this.isDraft,
      new_type: this.newType,
      new_state: this.newState,
      new_location: this.newLocation,
    }
  }
}

export default Comment

export type Comments = ReturnType<typeof Comment.reducer>
