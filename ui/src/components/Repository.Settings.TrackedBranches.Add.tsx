import React, { FunctionComponent, useEffect, useState } from "react"
import clsx from "clsx"

import InputAdornment from "@material-ui/core/InputAdornment"
import TextField from "@material-ui/core/TextField"
import CheckIcon from "@material-ui/icons/Check"
import Button from "@material-ui/core/Button"
import Typography from "@material-ui/core/Typography"
import { makeStyles } from "@material-ui/core/styles"
import Autocomplete from "@material-ui/lab/Autocomplete"

import Registry from "."
import FormGroup from "./Form.Group"
import { filtered, sorted, useRepository } from "../utils"
import { addTrackedBranch } from "../actions/trackedbranch"
import { useDispatch } from "../store"
import { rpcJSON } from "../utils/rpc"

const CHECK_REPOSITORY_TIMEOUT_MS = 1000

const useStyles = makeStyles((theme) => ({
  validUrlIcon: { color: theme.palette.success.main },

  blurb: {
    marginBottom: theme.spacing(2),
  },

  flex: {
    display: "flex",
    flexWrap: "wrap",
    alignContent: "end",
  },
  monospaceInput: {
    "& input": theme.critic.monospaceFont,
  },

  remoteName: {
    flexGrow: 1,
    marginRight: theme.spacing(1),
  },
  localName: {
    flexGrow: 1,
    marginLeft: theme.spacing(1),
  },
  autocompleteContainer: {
    flexGrow: 1,
    display: "flex",
    flexDirection: "column",
    justifyContent: "flex-end",
    paddingBottom: theme.spacing(1),
  },
  separator: {
    display: "flex",
    flexDirection: "column",
    justifyContent: "flex-end",
    padding: theme.spacing(1, 2),
    ...theme.critic.monospaceFont,
  },

  refsHeads: { "& p": theme.critic.monospaceFont },
  refOption: { display: "flex", width: "100%", ...theme.critic.monospaceFont },
  refName: { flexGrow: 1 },
  refValue: { flexGrow: 0 },

  center: {
    display: "flex",
    justifyContent: "space-around",
  },

  urlServer: {
    /*flexGrow: 1*/
  },
  urlPath: { flexGrow: 1 },

  error: {
    color: theme.palette.error.main,
    flexBasis: "100%",

    "& code": {
      ...theme.critic.monospaceFont,
    },
  },
}))

type LsRemoteResponse = {
  result?: {
    refs: { [ref: string]: string }
    symbolic_refs: { [ref: string]: string }
  }
  error?: {
    message: string
  }
}

type RemoteRef = {
  name: string
  sha1: string
}

const AddTrackedBranch: FunctionComponent = () => {
  const classes = useStyles()
  const dispatch = useDispatch()
  const [checkTimeoutID, setCheckTimeoutID] = useState<number | null>(null)
  const [urlValidation, setUrlValidation] = useState<true | false | null>(null)
  const [urlServer, setUrlServer] = useState("")
  const [urlPath, setUrlPath] = useState("")
  const [url, setUrl] = useState<string | null>(null)
  const [remoteName, setRemoteName] = useState("")
  const [remoteNameValue, setRemoteNameValue] = useState<RemoteRef | null>(null)
  const [localName, setLocalName] = useState("")
  const [remoteRefs, setRemoteRefs] = useState<RemoteRef[]>([])
  const repository = useRepository()

  const updateUrl = () => {
    setUrl(
      urlServer.trim() && urlPath.trim()
        ? `${urlServer.trim()}/${urlPath.trim()}`
        : null,
    )
    setUrlValidation(null)
  }

  const checkRepositoryNow = async (url: string) => {
    try {
      const { result, error } = await rpcJSON<LsRemoteResponse>("lsremote", {
        url,
        include_heads: true,
      })
      setUrlValidation(error === undefined)
      if (result)
        setRemoteRefs(
          sorted(
            filtered(Object.keys(result.refs), (refName) =>
              refName.startsWith("refs/heads/"),
            ),
          ).map((refName) => ({
            name: refName.substring(11),
            sha1: result.refs[refName],
          })),
        )
    } catch (error) {
      console.error(error)
    }
  }

  const checkRepository = (immediate: boolean) => (url: string) => {
    if (checkTimeoutID !== null) {
      window.clearTimeout(checkTimeoutID)
      setCheckTimeoutID(null)
    }
    setUrlValidation(false)
    if (immediate) {
      checkRepositoryNow(url)
    } else {
      setCheckTimeoutID(
        window.setTimeout(
          () => checkRepositoryNow(url),
          CHECK_REPOSITORY_TIMEOUT_MS,
        ),
      )
    }
  }

  useEffect(() => {
    if (url) checkRepositoryNow(url)
  }, [url])

  // useEffect(() => {
  //   if (urlValidation === true && remoteName.trim()) {
  //     rpcJSON<LsRemoteResponse>("lsremote", {
  //       url,
  //       refs: [`refs/heads/${remoteName}*`],
  //     }).then(({ result: { refs } = {} }) => {
  //       if (refs)
  //         setRemoteRefs(
  //           sorted(Object.keys(refs)).map((refName) => ({
  //             name: refName.substring(11),
  //             sha1: refs[refName],
  //           })),
  //         )
  //     })
  //   }
  // }, [url, remoteName, urlValidation])

  const urlError = urlValidation === false

  const add = (url: string) =>
    dispatch(
      addTrackedBranch(repository.id, localName || remoteName, {
        url,
        name: remoteName,
      }),
    )

  const separator = urlServer.indexOf("://") !== -1 ? "/" : ":"

  return (
    <>
      <FormGroup
        className={classes.flex}
        label="Repository URL"
        error={!!urlError}
      >
        <div className={classes.autocompleteContainer}>
          <Autocomplete
            id="url-server"
            className={classes.urlServer}
            freeSolo
            options={["https://github.com"]}
            onChange={(ev, value) => setUrlServer(value ?? "")}
            onInputChange={(ev, value) => setUrlServer(value ?? "")}
            onBlur={() => updateUrl()}
            renderInput={(params) => (
              <TextField
                {...params}
                className={classes.monospaceInput}
                label="Server"
              />
            )}
          />
        </div>
        <div className={classes.separator}>{separator}</div>
        <TextField
          id="url-path"
          className={clsx(classes.urlPath, classes.monospaceInput)}
          label="Path"
          value={urlPath}
          margin="normal"
          onChange={(ev) => {
            setUrlPath((ev.target as HTMLInputElement).value)
          }}
          onBlur={() => updateUrl()}
          InputProps={{
            endAdornment:
              urlValidation === true ? (
                <InputAdornment position="end">
                  <CheckIcon className={classes.validUrlIcon} />
                </InputAdornment>
              ) : undefined,
          }}
        />
        {urlError && (
          <Typography className={classes.error} variant="body2">
            Invalid repository URL: <code>{url}</code>
          </Typography>
        )}
      </FormGroup>

      <FormGroup className={classes.flex} label="Branch name">
        <Autocomplete
          id="remote-name-autocomplete"
          className={classes.remoteName}
          options={remoteRefs}
          getOptionLabel={(option) => option.name}
          value={remoteNameValue}
          onChange={(ev, value) => setRemoteNameValue(value)}
          inputValue={remoteName}
          onInputChange={(ev, value) => setRemoteName(value)}
          renderInput={(params) => (
            <TextField
              {...params}
              className={classes.monospaceInput}
              label="Remote"
              InputProps={{
                ...params.InputProps,
                startAdornment: (
                  <InputAdornment
                    position="start"
                    className={classes.refsHeads}
                  >
                    refs/heads/
                  </InputAdornment>
                ),
              }}
            />
          )}
          renderOption={(option) => (
            <div className={classes.refOption}>
              <span className={classes.refName}>{option.name}</span>{" "}
              <span className={classes.refValue}>
                {option.sha1.substring(0, 8)}
              </span>
            </div>
          )}
        />
        <TextField
          label="Local"
          className={clsx(classes.localName, classes.monospaceInput)}
          value={localName || remoteName}
          onChange={(ev) => setLocalName((ev.target as HTMLInputElement).value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start" className={classes.refsHeads}>
                refs/heads/
              </InputAdornment>
            ),
          }}
        />
      </FormGroup>
      <div className={classes.center}>
        <Button
          disabled={url === null}
          onClick={url ? () => add(url) : () => null}
          variant="contained"
          color="primary"
        >
          Add tracked branch
        </Button>
      </div>
    </>
  )
}

export default Registry.add(
  "Repository.Settings.TrackedBranches.Add",
  AddTrackedBranch,
)
