import React from "react"

import Button from "@material-ui/core/Button"

import Registry from "."
import Buttons from "./Settings.Buttons"

type Props = {
  isModified: boolean
  isSaving: boolean
  save: () => void
  reset: () => void
}

const SaveOrReset: React.FunctionComponent<Props> = ({
  isModified,
  isSaving,
  save,
  reset,
}) => (
  <Buttons>
    <Button disabled={!isModified} onClick={reset} variant="contained">
      Reset
    </Button>
    <Button
      disabled={isSaving || !isModified}
      onClick={save}
      variant="contained"
      color="primary"
    >
      Save
    </Button>
  </Buttons>
)

export default Registry.add("Settings.Buttons.SaveOrReset", SaveOrReset)
