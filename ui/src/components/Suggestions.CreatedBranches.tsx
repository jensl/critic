import React from "react"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import Branch from "./Suggestions.CreatedBranches.Branch"
import Panel from "./Suggestions.Panel"
import { loadCreated } from "../actions/branch"
import { id, useResource, useSignedInUser, useSubscriptionIf } from "../utils"

const useStyles = makeStyles((theme) => ({
  themeSwitch: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    width: "100%",
  },
  subtitle: { display: "block", marginRight: theme.spacing(2) },
  body: { display: "block" },
}))

type Props = {
  className?: string
}

const CreatedBranches: React.FunctionComponent<Props> = ({ className }) => {
  const classes = useStyles()
  const signedInUser = useSignedInUser()
  useSubscriptionIf(signedInUser !== null, loadCreated, id(signedInUser))
  const branches = useResource("branches", ({ created }) => created)
  if (branches.length === 0) return null
  return (
    <Panel
      className={className}
      panelID="createdBranches"
      heading="Created branches"
      subheading="Branches you may want to request reviews of"
      reasons={branches.map((branchID) => (
        <Branch key={branchID} branchID={branchID} />
      ))}
    ></Panel>
  )
}

export default Registry.add("Suggestions.CreatedBranches", CreatedBranches)
