import { AutomaticMode } from "../actions"

export type ActionProps = {
  variant: "unified" | "side-by-side"
  integrated: boolean
  automaticMode?: AutomaticMode
  setAutomaticMode?: (mode: AutomaticMode) => void
}
