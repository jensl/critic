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

import { createMuiTheme } from "@material-ui/core/styles"
import red from "@material-ui/core/colors/red"
import teal from "@material-ui/core/colors/teal"
import green from "@material-ui/core/colors/green"
import lightGreen from "@material-ui/core/colors/lightGreen"
import blue from "@material-ui/core/colors/blue"
import orange from "@material-ui/core/colors/orange"
import amber from "@material-ui/core/colors/amber"
import lightBlue from "@material-ui/core/colors/lightBlue"
import grey from "@material-ui/core/colors/grey"
import blueGrey from "@material-ui/core/colors/blueGrey"
import yellow from "@material-ui/core/colors/yellow"
import deepOrange from "@material-ui/core/colors/deepOrange"
import { Color } from "@material-ui/core"
import { TypographyOptions } from "@material-ui/core/styles/createTypography"

declare module "@material-ui/core/styles/createMuiTheme" {
  interface Theme {
    critic: any
  }
  interface ThemeOptions {
    critic: any
  }
}

declare module "@material-ui/core/styles/createPalette" {
  interface Palette {
    issue: { open: string; closed: string }
    note: string
  }
  interface PaletteOptions {
    issue: { open: string; closed: string }
    note: string
  }
}

const typography: TypographyOptions = {
  fontFamily: "Lato, sans-serif",
  caption: { fontSize: "0.8rem" },
  button: { fontWeight: 700 },
}

export const lightTheme = createMuiTheme({
  typography,

  palette: {
    type: "light",
    primary: { main: red["A700"] },
    secondary: { main: teal[100], light: teal[50] },
    success: { main: green[500] },
    issue: { open: red["A700"], closed: green[500] },
    note: yellow[700],
  },

  critic: {
    monospaceFont: {
      fontFamily: "Fira Code, monospace",
      fontSize: "10pt",
    },
    syntax: {
      operator: { fontWeight: 700 },
      identifier: { fontWeight: 400 },
      keyword: { fontWeight: 700 },
      character: {},
      string: { color: blue[900] },
      comment: { color: red["A700"] },
      integer: {},
      number: {},
      ppDirective: {},
    },
    diff: {
      base: { color: "#000" },
      background: { backgroundColor: "hsla(45, 25%, 90%, 1)" },
      context: { backgroundColor: "#fff" },
      deletedLine: { backgroundColor: red[100] },
      deletedCode: { backgroundColor: red[100] },
      deletedCodeDark: { backgroundColor: red[200] },
      insertedLine: { backgroundColor: lightGreen[200] },
      insertedCode: { backgroundColor: lightGreen[200] },
      insertedCodeDark: { backgroundColor: lightGreen[300] },
      modifiedLineOld: { backgroundColor: amber[100] },
      modifiedLineNew: { backgroundColor: amber[100] },
    },
    selectionRectangle: {
      borderWidth: 2,
      borderStyle: "dashed",
      borderColor: "#888",
      borderRadius: 4,
    },
    standout: {
      backgroundColor: teal[50],
      borderColor: teal[100],
      borderWidth: 1,
      borderStyle: "solid",
      borderRadius: 4,
      padding: "1px 6px",
    },
  },
})

export const darkTheme = createMuiTheme({
  typography,

  palette: {
    type: "dark",
    primary: { main: red[300], dark: red[500] },
    secondary: { main: teal[400], light: teal[700], contrastText: grey[200] },
    success: { main: green[500] },
    text: { primary: amber[50] },
    issue: { open: red[900], closed: green[500] },
    note: yellow[700],
  },

  critic: {
    monospaceFont: {
      fontFamily: "Fira Code, monospace",
      fontSize: "10pt",
    },
    syntax: {
      base: { color: "#72696a" },
      operator: { fontWeight: 500 },
      identifier: { fontWeight: 400, color: "#fff1f3" },
      keyword: { fontWeight: 700, color: "#f66883" },
      character: {},
      string: { color: "#f9cc6c" },
      comment: {},
      integer: {},
      number: {},
      ppDirective: {},
    },
    diff: {
      background: { backgroundColor: "#2c2525" }, //"#484848" },
      border: { border: "1px solid #594b4b" },
      context: { backgroundColor: "#2c2525" }, //"#383838" },
      deletedLine: { backgroundColor: "#422b2e" }, // "hsla(0, 66%, 36%, 35%)" },
      deletedCode: { backgroundColor: "#422b2e" }, // "hsla(0, 66%, 36%, 35%)" },
      deletedCodeDark: { backgroundColor: "#553136" }, // "hsla(0, 66%, 40%, 35%)" },
      insertedLine: { backgroundColor: "#373a2c" }, //"hsla(95, 40%, 36%, 35%)" },
      insertedCode: { backgroundColor: "#373a2c" }, //"hsla(95, 40%, 36%, 35%)" },
      insertedCodeDark: { backgroundColor: "#464734" }, //"hsla(95, 40%, 40%, 35%)" },
      modifiedLineOld: { backgroundColor: "#353021" }, //"hsla(45, 100%, 60%, 35%)" },
      modifiedLineNew: { backgroundColor: "#353021" }, // "hsla(45, 100%, 60%, 35%)" },
    },
    selectionRectangle: {
      borderWidth: 2,
      borderStyle: "dashed",
      borderColor: lightBlue[200],
      borderRadius: 4,
    },
    standout: {
      backgroundColor: teal[800],
      borderColor: teal[700],
      borderWidth: 1,
      borderStyle: "solid",
      borderRadius: 4,
      padding: "1px 6px",
    },
  },

  overrides: {
    // MuiInputLabel: {
    //   root: {
    //     "&$focused": {
    //       color: red[500],
    //     },
    //   },
    // },
    // MuiOutlinedInput: {
    //   root: {
    //     "&$focused $notchedOutline": {
    //       borderColor: red[500],
    //       borderWidth: "1px",
    //     },
    //   },
    // },
  },
})
