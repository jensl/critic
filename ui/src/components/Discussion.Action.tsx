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

import React from "react"

import Button from "@material-ui/core/Button"
import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import clsx from "clsx"

export type ActionProps = {
  className?: string
  size?: "small" | "medium" | "large"
  disabled?: boolean
  color?: "primary" | "secondary"
  variant?: "text" | "outlined" | "contained"
}

const useStyles = makeStyles((theme) => ({
  action: {
    marginLeft: theme.spacing(1),
  },
}))

type OwnProps = {
  onClick: () => void
}

const Action: React.FunctionComponent<ActionProps & OwnProps> = ({
  className,
  size = "small",
  children,
  ...buttonProps
}) => {
  const classes = useStyles()
  return (
    <Button
      className={clsx(className, classes.action)}
      size={size}
      onMouseDown={(ev) => ev.stopPropagation()}
      {...buttonProps}
    >
      {children}
    </Button>
  )
}

export default Registry.add("Discussion.Action", Action)
