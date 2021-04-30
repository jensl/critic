import React, { useEffect, useMemo, useState } from "react"

import TablePagination from "@material-ui/core/TablePagination"
import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import BranchList from "./Branch.List"
import { loadRepositoryBranches } from "../actions/branch"
import { BranchID } from "../resources/types"
import { useDispatch } from "../store"
import { useRepository } from "../utils"
import Breadcrumb from "./Breadcrumb"
import SetPrefix from "../utils/PrefixContext"
import Pagination from "../utils/Pagination"
import Branch from "../resources/branch"
import { filterNulls } from "../utils/Functions"

const useStyles = makeStyles((theme) => ({
  pagination: {
    display: "flex",
    justifyContent: "space-around",
  },
}))

const RepositoryBranches: React.FunctionComponent = () => {
  const classes = useStyles()
  const dispatch = useDispatch()
  const repository = useRepository()
  const [branchIDs, setBranchIDs] = useState<BranchID[]>([])
  const [offset, setOffset] = useState(0)
  const [count, setCount] = useState(10)
  const [total, setTotal] = useState(0)

  // useEffect(() => {
  //   if (repository)
  //     dispatch(
  //       loadRepositoryBranches(repository.id, offset, count),
  //     ).then((branchs) => setBranchIDs(branchs.map((branch) => branch.id)))
  // }, [dispatch, repository?.id, offset, count])

  const pagination = useMemo(
    () =>
      new Pagination<Branch>(
        "Repository.Branches",
        (offset, count) => {
          console.log("fetching branches", { offset, count })
          return loadRepositoryBranches(repository.id, offset, count)
        },
        (state, branchIDs) => {
          console.log("retrieving branches", branchIDs)
          return [
            ...filterNulls(
              branchIDs.map((branchID) =>
                state.resource.branches.byID.get(branchID),
              ),
            ),
          ]
        },
      ),
    [repository.id],
  )

  useEffect(() => {
    if (!pagination) return
    const [cached, fetched] = pagination.fetchRange(dispatch, offset, count)
    setTotal(cached.total)
    setBranchIDs(cached.items.map((branch) => branch.id))
    fetched.then(({ total, items: branches }) => {
      setTotal(total)
      setBranchIDs(branches.map((branch) => branch.id))
    })
  }, [pagination, dispatch, offset, count])

  if (!repository) return null

  return (
    <Breadcrumb label="branches">
      <SetPrefix prefix={`/repository/${repository.name}`}>
        <BranchList branchIDs={branchIDs} />
      </SetPrefix>
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
    </Breadcrumb>
  )
}

export default Registry.add("Repository.Branches", RepositoryBranches)
