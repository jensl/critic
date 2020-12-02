/*
 * Copyright 2019 the Critic contributors, Opera Software ASA
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

import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Typography from "@material-ui/core/Typography"

import Registry from "."
import { useLocation } from "react-router"

const useStyles = makeStyles((theme) => ({
  applicationNotFound: {
    display: "flex",
    alignItems: "flex-start",
    lineHeight: "160px",
  },
  statusCode: {
    ...theme.critic.monospaceFont,
    fontSize: "200px",
    lineHeight: "inherit",
    textAlign: "right",

    marginLeft: "20%",
    paddingRight: "40px",
    borderRight: "1px solid rgba(128, 128, 128, 0.5)",
    marginRight: "40px",

    paddingBottom: "15px",
  },
  message: {
    lineHeight: "inherit",
  },
  path: {
    ...theme.critic.monospaceFont,
    ...theme.critic.standout,
  },
}))

type OwnProps = {
  className?: string
}

type ConnectedProps = {}

const NotFound: FunctionComponent<OwnProps & ConnectedProps> = ({
  className,
}) => {
  const classes = useStyles()
  const { pathname } = useLocation()
  return (
    <div className={clsx(className, classes.applicationNotFound)}>
      <div className={classes.statusCode}>404</div>
      <Typography variant="body1" className={classes.message}>
        Not a valid path: <span className={classes.path}>{pathname}</span>
      </Typography>
    </div>
  )
}

export default Registry.add("Application.NotFound", NotFound)
