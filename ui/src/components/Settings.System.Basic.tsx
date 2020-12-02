import React from "react"

import Registry from "."
import Section from "./Settings.System.Section"
import SaveOrReset from "./Settings.Buttons.SaveOrReset"
import TextField from "./Settings.System.TextField"
import FormGroup from "./Form.Group"
import Checkbox from "./Settings.System.Checkbox"
import useConnectedControls from "../utils/ConnectedControls"
import { useSubscription } from "../utils"
import { loadSystemSettingByPrefix } from "../actions/system"

const Contents: React.FunctionComponent<{}> = () => {
  const {
    isModified,
    isSaving,
    save,
    reset,
    connectedControlProps,
  } = useConnectedControls()

  useSubscription(loadSystemSettingByPrefix, "system")

  return (
    <>
      <FormGroup label="System settings">
        <TextField
          settingKey="system.hostname"
          label="Hostname"
          {...connectedControlProps}
          TextFieldProps={{
            fullWidth: true,
            inputProps: { spellCheck: false },
          }}
        />
        <Checkbox
          settingKey="system.is_development"
          label="Development mode"
          {...connectedControlProps}
        />
      </FormGroup>
      <SaveOrReset
        isModified={isModified}
        isSaving={isSaving}
        save={save}
        reset={reset}
      />
    </>
  )
}

const Basic: React.FunctionComponent<{}> = () => (
  <Section id="details" title="Basic system settings">
    <Contents />
  </Section>
)

export default Registry.add("Settings.System.Basic", Basic)
