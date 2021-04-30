import React, { FunctionComponent } from "react"
import { useLocation } from "react-router"
import clsx from "clsx"

import Container from "@material-ui/core/Container"
import { makeStyles, Theme } from "@material-ui/core/styles"

import Registry from "."
import Breadcrumb from "./Breadcrumb"
import ContributingCommits from "./Changeset.ContributingCommits"
import Changeset from "./Changeset"
import ProgressPopup from "./Changeset.ProgressPopup"
import { loadChangesetBySHA1 } from "../actions/changeset"
import {
  id,
  useRepository,
  useResource,
  useResourceExtra,
  useOptionalReview,
  useSubscription,
} from "../utils"
import { parseExpandedFiles, useChangesetByRefs } from "../utils/Changeset"
import { SetChangeset } from "../utils/ChangesetContext"
import { nullBecause } from "../debug"
import LoaderBlock from "./Loader.Block"

const useStyles = makeStyles((theme: Theme) => ({
  root: {},
  commitListContainer: {
    marginBottom: theme.spacing(3),

    [theme.breakpoints.down("xs")]: {
      paddingLeft: theme.spacing(0),
      paddingRight: theme.spacing(0),
    },
  },
  commitListPaper: {
    padding: theme.spacing(1, 2),
  },
}))

type Props = {
  className?: string
  fromCommitRef: string
  toCommitRef: string
}

const ChangesetRange: FunctionComponent<Props> = ({
  className,
  fromCommitRef,
  toCommitRef,
}) => {
  const classes = useStyles()
  const location = useLocation()

  /*const repository = useRepository()
  const review = useOptionalReview()

  useSubscription(loadChangesetBySHA1, [
    {
      refs: { fromCommitRef, toCommitRef },
      repositoryID: id(repository),
      reviewID: id(review),
    },
  ])

  const changesets = useResource("changesets")
  const commits = useResource("commits")
  const commitRefs = useResourceExtra("commitRefs")

  if (!repository) return nullBecause("no repository")

  const fromCommitID = commitRefs.get(`${repository.id}:${fromCommitRef}`)
  if (typeof fromCommitID !== "number")
    return nullBecause(
      `no fromCommitID: "${repository.id}:${fromCommitRef}" not in commitRefs`,
    )
  const fromCommit = commits.byID.get(fromCommitID)
  if (!fromCommit)
    return nullBecause(`no fromCommit: ${fromCommitID} not in commits.byID`)
  const toCommitID = commitRefs.get(`${repository.id}:${toCommitRef}`)
  if (typeof toCommitID !== "number")
    return nullBecause(
      `no toCommitID: "${repository.id}:${toCommitRef}" not in commitRefs`,
    )
  const toCommit = commits.byID.get(toCommitID)
  if (!toCommit)
    return nullBecause(`no toCommit: ${toCommitID} not in commits.byID`)
  const changesetID = changesets.byCommits.get(
    `${fromCommit.id}..${toCommit.id}`,
  )
  if (typeof changesetID !== "number")
    return nullBecause(
      `no changesetID: ${fromCommit.id}..${toCommit.id} not in changesets.byCommits`,
    )
  const changeset = changesets.byID.get(changesetID)
  if (!changeset)
    return nullBecause(`no changeset: ${changesetID} not in changesets.byID`)*/

  const changeset = useChangesetByRefs({ fromCommitRef, toCommitRef })
  const fromSHA1 = useResource(
    "commits",
    ({ byID }) =>
      byID.get(changeset?.fromCommit ?? -1)?.sha1.substring(0, 8) ?? "",
  )
  const toSHA1 = useResource(
    "commits",
    ({ byID }) =>
      byID.get(changeset?.toCommit ?? -1)?.sha1.substring(0, 8) ?? "",
  )

  if (!changeset) return <LoaderBlock />

  const expandedFileIDs = parseExpandedFiles(location)
  return (
    <Breadcrumb category="diff" label={`${fromSHA1}..${toSHA1}`}>
      <SetChangeset changeset={changeset} expandedFileIDs={expandedFileIDs}>
        {changeset.contributingCommits && (
          <Container
            className={clsx(className, classes.commitListContainer)}
            maxWidth="md"
          >
            <ContributingCommits />
          </Container>
        )}
        <Changeset />
        <ProgressPopup />
      </SetChangeset>
    </Breadcrumb>
  )
}

export default Registry.add("Changeset.Range", ChangesetRange)
