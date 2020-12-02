import React from "react"

import Button from "@material-ui/core/Button"

import Registry from "."
import { ActionProps } from "./Changeset.Action"
import { useChangeset, useRepository, useResource, useReview } from "../utils"
import { useExpandedFiles } from "../actions/uiFileDiff"
import { useHistory, useLocation } from "react-router"
import { generateLinkPath, pathWithExpandedFiles } from "../utils/Changeset"

const SideBySide: React.FunctionComponent<ActionProps> = ({ integrated }) => {
  const history = useHistory()
  const review = useReview()
  const repository = useRepository()
  const { changeset, expandedFileIDs } = useChangeset()
  const commitByID = useResource("commits", ({ byID }) => byID)
  if (!integrated) return null
  const prefix = review
    ? `/review/${review.id}`
    : repository
    ? `/repository/${repository.id}`
    : null
  const toCommit = commitByID.get(changeset.toCommit)
  const fromCommit = commitByID.get(changeset.fromCommit)
  if (!prefix || !toCommit || !fromCommit) return null
  const diff = changeset.isDirect
    ? `commit/${toCommit.sha1}`
    : `diff/${fromCommit.sha1}..${toCommit.sha1}`
  return (
    <Button
      onClick={() =>
        history.replace(
          pathWithExpandedFiles(
            { pathname: `${prefix}/${diff}` },
            expandedFileIDs,
          ),
        )
      }
    >
      Side-by-side
    </Button>
  )
}

export default Registry.add("Changeset.Action.SideBySide", SideBySide)
