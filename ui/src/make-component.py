#!/usr/bin/python3

import argparse
import contextlib
import os

CONTAINER = """\
/*
 * Copyright 2017 the Critic contributors, Opera Software ASA
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

import { connect } from "react-redux"

import %(name)s from "./presentation"

const mapStateToProps = state => ({

})

const mapDispatchToProps = dispatch => ({

})

export default connect(mapStateToProps, mapDispatchToProps)(%(name)s)
"""

COMPONENT = """\
/*
 * Copyright 2017 the Critic contributors, Opera Software ASA
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

import "./stylesheet.css"

const %(name)s = props => {
    return <div/>
}

export default %(name)s
"""

STYLESHEET = """\
/*
 * Copyright 2017 the Critic contributors, Opera Software ASA
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
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    arguments = parser.parse_args()

    src_dir = os.path.dirname(os.path.abspath(__file__))
    component_name = arguments.name.split("/")
    if component_name[0] == "components":
        del component_name[0]
    component_dir = os.path.join(src_dir, "components", *component_name)
    assert os.path.isdir(os.path.dirname(component_dir))

    os.mkdir(component_dir)

    @contextlib.contextmanager
    def xopen(filename):
        path = os.path.join(component_dir, filename)
        file = open(path, "w")
        try:
            yield file
        except:
            os.unlink(path)
            raise

    parameters = {"name": os.path.basename(component_dir)}

    with xopen("index.js") as container, xopen("presentation.js") as component, xopen(
        "stylesheet.css"
    ) as stylesheet:
        container.write(CONTAINER % parameters)
        component.write(COMPONENT % parameters)
        stylesheet.write(STYLESHEET % parameters)


if __name__ == "__main__":
    main()
