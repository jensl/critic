import React, { useEffect, useState } from "react"

import Checkbox, { CheckboxProps } from "@material-ui/core/Checkbox"
import Typography from "@material-ui/core/Typography"
import FormControlLabel from "@material-ui/core/FormControlLabel"

import Registry from "."
import { useSystemSetting } from "../utils/SystemSetting"
import { ConnectedControlProps } from "../utils/ConnectedControls"

type Props = {
  className?: string
  settingKey: string
  label: string
  CheckboxProps?: Partial<CheckboxProps>
}

const SystemSettingCheckbox: React.FunctionComponent<
  Props & ConnectedControlProps
> = ({
  className,
  settingKey,
  label,
  setSave,
  resetCounter,
  CheckboxProps = {},
}) => {
  const [currentValue, saveValue, description] = useSystemSetting<
    boolean | null
  >(settingKey)
  const [newValue, setNewValue] = useState<boolean | null>(null)

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
    <FormControlLabel
      control={
        <Checkbox
          key={`${currentValue}-${resetCounter}`}
          className={className}
          disabled={currentValue === undefined}
          defaultChecked={!!currentValue}
          onChange={(ev) => setNewValue(ev.target.checked)}
          {...CheckboxProps}
        />
      }
      label={
        <>
          {label}
          <Typography variant="caption" display="block" color="textSecondary">
            {description}
          </Typography>
        </>
      }
    />
  )
}

export default Registry.add("System.Setting.Checkbox", SystemSettingCheckbox)
