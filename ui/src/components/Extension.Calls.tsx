import React, { FunctionComponent, useState } from "react"
import clsx from "clsx"

import Button from "@material-ui/core/Button"
import Container from "@material-ui/core/Container"
import Dialog from "@material-ui/core/Dialog"
import DialogActions from "@material-ui/core/DialogActions"
import DialogContent from "@material-ui/core/DialogContent"
import DialogTitle from "@material-ui/core/DialogTitle"
import { DataGrid, GridColDef } from "@material-ui/data-grid"
import ArrowLeftIcon from "@material-ui/icons/ArrowLeft"
import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import MarkdownDocument from "./Markdown.Document"
import { useExtensionVersion } from "../utils/ExtensionContext"
import {
  filtered,
  last,
  sortedBy,
  useResource,
  useSubscriptionIf,
} from "../utils"
import {
  loadExtensionCallsByVersion,
  repeatExtensionCall,
} from "../actions/extension"
import timeSince from "../utils/TimeSince"
import ExtensionCall, { CallRequest } from "../resources/extensioncall"
import { useDispatch } from "../store"

const useStyles = makeStyles((theme) => ({
  extensionCalls: { display: "flex", height: "100%" },
  gridContainer: { flexGrow: 1, padding: theme.spacing(1, 2) },
  grid: { border: "none" },

  monospace: {
    ...theme.critic.monospaceFont,
  },
  standout: {
    ...theme.critic.standout,
  },

  description: {
    display: "inline-flex",
    alignItems: "baseline",
    lineHeight: 1.5,

    "& code": {
      marginLeft: theme.spacing(1),
    },
  },
}))

type OwnProps = {
  className?: string
}

type Row = {
  call: ExtensionCall
  id: string
  time: number
  duration: "pending" | number
  description: () => JSX.Element
  classes: ReturnType<typeof useStyles>
}

const columns: GridColDef[] = [
  {
    field: "id",
    headerName: "Id",
    flex: 2,
    renderCell: (params) => {
      const row = params.row as Row
      return <code className={row.classes.monospace}>{row.id}</code>
    },
  },
  {
    field: "time",
    headerName: "Time",
    flex: 1,
    valueFormatter: (params) => timeSince((params.row as Row).time) + " ago",
  },
  {
    field: "duration",
    headerName: "Duration",
    flex: 1,
    valueFormatter: (params) => {
      let row = params.row as Row
      let duration = row.duration
      if (duration === "pending") return "pending"
      if (duration < 60) return `${duration.toPrecision(3)}s`
      duration = duration / 60
      if (duration < 60) return `${duration.toPrecision(3)}m`
      duration = duration / 60
      if (duration < 24) return `${duration.toPrecision(3)}h`
      duration = duration / 24
      return `${duration.toPrecision(3)}d`
    },
  },
  {
    field: "_description",
    headerName: "Description",
    flex: 6,
    renderCell: (params) => {
      const row = params.row as Row
      return (
        <span className={row.classes.description}>{row.description()}</span>
      )
    },
  },
]

const ExtensionCalls: FunctionComponent<OwnProps> = ({ className }) => {
  const classes = useStyles()
  const dispatch = useDispatch()
  const [selectedCall, setSelectedCall] = useState<ExtensionCall | null>(null)
  const version = useExtensionVersion()
  useSubscriptionIf(!!version, loadExtensionCallsByVersion, [version!])
  const rows = useResource("extensioncalls", (byID) =>
    sortedBy(
      filtered(byID.values(), (call) => call.version === version?.id),
      (call) => call.requestTime,
    ).map(
      (call): Row => {
        const description = (request: CallRequest) => () => {
          switch (request.type) {
            case "endpoint": {
              return (
                <>
                  endpoint::{request.name}:
                  <code className={clsx(classes.monospace, classes.standout)}>
                    {request.request.method} {request.request.path}
                  </code>
                </>
              )
            }
            case "subscription": {
              return (
                <>
                  subscription:
                  <code className={clsx(classes.monospace, classes.standout)}>
                    {request.message.channel}
                  </code>
                  <code className={clsx(classes.monospace, classes.standout)}>
                    {last(request.message.payload.__type__.split("."))}
                  </code>
                </>
              )
            }
          }
        }
        return {
          call,
          id: call.id,
          time: call.requestTime,
          duration: call.responseTime
            ? call.responseTime - call.requestTime
            : "pending",
          description: description(call.request),
          classes,
        }
      },
    ),
  )
  if (!version) return null

  const repeat = (call: ExtensionCall) =>
    dispatch(repeatExtensionCall(call)).then(setSelectedCall)

  return (
    <div className={classes.extensionCalls}>
      <div className={classes.gridContainer}>
        <DataGrid
          className={classes.grid}
          columns={columns}
          rows={rows}
          onRowClick={({ row }) => setSelectedCall(row.call)}
          getRowId={(call) => call.id}
          selectionModel={selectedCall ? [selectedCall.id] : []}
        />
        {selectedCall !== null && (
          <Dialog open onClose={() => setSelectedCall(null)}>
            <DialogTitle>
              Call: <code>{selectedCall.id}</code>
            </DialogTitle>
            <DialogContent>Lorem ipsum.</DialogContent>
            <DialogActions>
              <Button onClick={() => repeat(selectedCall)} color="primary">
                Repeat call
              </Button>
            </DialogActions>
          </Dialog>
        )}
      </div>
    </div>
  )
}

//export default Registry.add("Extension.Calls", ExtensionCalls)

export default ExtensionCalls
