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

import { combineReducers } from "redux"
import { immerable } from "immer"

import {
  CommentType,
  CommentID,
  ReplyID,
  ReviewableFileChangeID,
  ReviewID,
} from "./types"
import { ResourceData } from "../types"
import { primaryMap } from "../reducers/resource"

interface BatchProps {
  id: null | number
  is_empty: boolean
  review: number
  author: number
  comment: null | number
  timestamp: number
  created_comments: CommentID[]
  written_replies: ReplyID[]
  reopened_issues: CommentID[]
  resolved_issues: CommentID[]
  morphed_comments: CommentID[]
  reviewed_changes: ReviewableFileChangeID[]
  unreviewed_changes: ReviewableFileChangeID[]
}

export class Batch {
  [immerable] = true

  constructor(
    readonly id: null | number,
    readonly isEmpty: boolean,
    readonly review: number,
    readonly author: number,
    readonly comment: null | number,
    readonly timestamp: number,
    readonly createdComments: CommentID[],
    readonly writtenReplies: ReplyID[],
    readonly reopenedIssues: CommentID[],
    readonly resolvedIssues: CommentID[],
    readonly morphedComments: CommentID[],
    readonly reviewedChanges: ReviewableFileChangeID[],
    readonly unreviewedChanges: ReviewableFileChangeID[],
  ) {}

  static new(props: BatchProps) {
    return new Batch(
      props.id,
      props.is_empty,
      props.review,
      props.author,
      props.comment,
      props.timestamp,
      props.created_comments,
      props.written_replies,
      props.reopened_issues,
      props.resolved_issues,
      props.morphed_comments,
      props.reviewed_changes,
      props.unreviewed_changes,
    )
  }

  static prepare(value: ResourceData) {
    return {
      ...value,
      morphed_comments: value.morphed_comments.map(MorphedComment.new),
    }
  }

  static reducer = combineReducers({
    byID: primaryMap<Batch, number>("batches"),

    // FIXME: Should clear this map when signing out.
    unpublished: primaryMap<Batch, ReviewID>("batches", (batch) =>
      batch.id === null ? batch.review : null,
    ),
  })

  get props(): BatchProps {
    return {
      ...this,
      is_empty: this.isEmpty,
      created_comments: this.createdComments,
      written_replies: this.writtenReplies,
      reopened_issues: this.reopenedIssues,
      resolved_issues: this.resolvedIssues,
      morphed_comments: this.morphedComments,
      reviewed_changes: this.reviewedChanges,
      unreviewed_changes: this.unreviewedChanges,
    }
  }
}

interface MorphedCommentProps {
  comment: CommentID
  new_type: CommentType
}

class MorphedComment {
  [immerable] = true

  constructor(readonly comment: number, readonly newType: CommentType) {}

  static new(props: MorphedCommentProps) {
    return new MorphedComment(props.comment, props.new_type)
  }
}

export default Batch
