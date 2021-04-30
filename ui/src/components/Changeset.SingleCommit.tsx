import React, { FunctionComponent } from "react"
import { useLocation } from "react-router"
import clsx from "clsx"

import { makeStyles, Theme } from "@material-ui/core/styles"
import Container from "@material-ui/core/Container"

import Registry from "."
import ChangesetCommit from "./Changeset.Commit"
import Changeset from "./Changeset"
import ProgressPopup from "./Changeset.ProgressPopup"
import LoaderBlock from "./Loader.Block"
import { loadChangesetBySHA1 } from "../actions/changeset"
import { id, useRepository, useOptionalReview, useSubscription } from "../utils"
import { parseExpandedFiles, useChangesetByRefs } from "../utils/Changeset"
import { SetChangeset } from "../utils/ChangesetContext"
import Commit from "../resources/commit"
import { useSelector } from "../store"

const useStyles = makeStyles((theme: Theme) => ({
  root: {},
  commitContainer: {
    marginBottom: theme.spacing(3),

    [theme.breakpoints.down("xs")]: {
      paddingLeft: theme.spacing(0),
      paddingRight: theme.spacing(0),
    },
  },
}))

type Props = {
  className?: string
  commit: Commit
}

const ChangesetSingleCommit: FunctionComponent<Props> = ({
  className,
  commit,
}) => {
  const classes = useStyles()
  const location = useLocation()
  /*const repository = useRepository()
  const review = useOptionalReview()
  const changesets = useSelector((state) => state.resource.changesets)
  const context = review
    ? { reviewID: review.id }
    : { repositoryID: repository.id }
  useSubscription(loadChangesetBySHA1, [
    {
      refs: { singleCommitRef: String(commit.id) },
      ...context,
    },
  ])
  const changesetID = changesets.byCommits.get(String(commit.id))
  const changeset = changesets.byID.get(Number(changesetID))*/
  const changeset = useChangesetByRefs({ singleCommitRef: String(commit.id) })
  if (!changeset) return <LoaderBlock />
  const expandedFileIDs = parseExpandedFiles(location)
  return (
    <SetChangeset changeset={changeset} expandedFileIDs={expandedFileIDs}>
      <Container
        className={clsx(className, classes.commitContainer)}
        maxWidth="md"
      >
        <ChangesetCommit commit={commit} />
      </Container>
      <Changeset />
      <ProgressPopup />
    </SetChangeset>
  )
}

export default Registry.add("Changeset.SingleCommit", ChangesetSingleCommit)
