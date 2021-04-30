import React, { FunctionComponent, useEffect, useMemo, useState } from "react"
import clsx from "clsx"

import Container from "@material-ui/core/Container"
import Paper from "@material-ui/core/Paper"
import TablePagination from "@material-ui/core/TablePagination"
import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import CommitList from "./Commit.List"
import { loadBranchCommits } from "../actions/branch"
import { usePrefix, useBranch } from "../utils"
import Pagination from "../utils/Pagination"
import { filterNulls } from "../utils/Functions"
import Commit from "../resources/commit"
import { CommitID } from "../resources/types"
import { useDispatch } from "../store"

const useStyles = makeStyles((theme) => ({
  branchCommits: {
    padding: `${theme.spacing(1)}px ${theme.spacing(3)}px`,
  },
  pagination: {
    display: "flex",
    justifyContent: "space-around",
  },
}))

type Props = {
  className?: string
  offset?: number
  count?: number
}

const BranchCommits: FunctionComponent<Props> = ({ className }) => {
  const classes = useStyles()
  const dispatch = useDispatch()
  const prefix = usePrefix()
  const branch = useBranch()
  const [commitIDs, setCommitIDs] = useState<CommitID[]>([])
  const [offset, setOffset] = useState(0)
  const [count, setCount] = useState(10)
  const [total, setTotal] = useState(0)

  const pagination = useMemo(
    () =>
      new Pagination<Commit>(
        "Branch.Commits",
        (offset, count) => loadBranchCommits(branch.id, offset, count),
        (state, commitIDs) => [
          ...filterNulls(
            commitIDs.map((commitID) =>
              state.resource.commits.byID.get(commitID),
            ),
          ),
        ],
      ),
    [branch.id],
  )

  useEffect(() => {
    if (!pagination) return
    const [cached, fetched] = pagination.fetchRange(dispatch, offset, count)
    setTotal(cached.total)
    setCommitIDs(cached.items.map((commit) => commit.id))
    fetched.then(({ total, items: commits }) => {
      setTotal(total)
      setCommitIDs(commits.map((commit) => commit.id))
    })
  }, [pagination, dispatch, offset, count])

  return (
    <>
      <Container maxWidth="lg">
        <Paper className={clsx(className, classes.branchCommits)}>
          <CommitList scopeID={`branch_${branch.id}`} commitIDs={commitIDs} />
        </Paper>
      </Container>
      <TablePagination
        className={classes.pagination}
        component="div"
        count={total}
        page={offset / count}
        rowsPerPage={count}
        onChangePage={(_, newPage) => setOffset(newPage * count)}
        onChangeRowsPerPage={(ev) => {
          const newCount = parseInt((ev.target as HTMLInputElement).value, 10)
          setOffset(Math.floor(offset / newCount) * newCount)
          setCount(newCount)
        }}
      />
    </>
  )
}

export default Registry.add("Branch.Commits", BranchCommits)
