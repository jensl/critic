import React, { useEffect, useState } from "react"

import TextField, { TextFieldProps } from "@material-ui/core/TextField"

import Registry from "."
import { useSystemSetting } from "../utils/SystemSetting"
import { ConnectedControlProps } from "../utils/ConnectedControls"

type Props = {
  className?: string
  settingKey: string
  label: string
  TextFieldProps?: Partial<TextFieldProps>
}

const SystemSettingTextField: React.FunctionComponent<
  Props & ConnectedControlProps
> = ({
  className,
  settingKey,
  label,
  setSave,
  resetCounter,
  TextFieldProps = {},
}) => {
  const [currentValue, saveValue, description] = useSystemSetting<
    string | null
  >(settingKey)
  const [newValue, setNewValue] = useState<string | null>(null)

  useEffect(() => {
    const callback = async () => void (await saveValue(newValue))
    setSave(
      settingKey,
      newValue !== null && currentValue !== newValue ? callback : null,
    )
  }, [newValue, currentValue])

  useEffect(() => {
    setNewValue(null)
  }, [resetCounter])

  return (
    <TextField
      key={`${currentValue}-${resetCounter}`}
      disabled={currentValue === undefined}
      className={className}
      label={label}
      defaultValue={currentValue}
      margin="normal"
      onChange={(ev) => setNewValue(ev.target.value)}
      helperText={description}
      {...TextFieldProps}
    />
  )
}

export default Registry.add("System.Setting.TextField", SystemSettingTextField)
