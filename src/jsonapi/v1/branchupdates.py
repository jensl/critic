# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2015 the Critic contributors, Opera Software ASA
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License.  You may obtain a copy of
# the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
# License for the specific language governing permissions and limitations under
# the License.

import api
import jsonapi

@jsonapi.PrimaryResource
class BranchUpdates(object):
    """Branch updates in the Git repositories."""

    name = "branchupdates"
    contexts = (None, "branches", "reviews")
    value_class = api.branchupdate.BranchUpdate
    exceptions = api.branchupdate.InvalidBranchUpdateId

    @staticmethod
    def json(value, parameters):
        """BranchUpdate {
             "id": integer, // the branch update's id
             "branch": integer, // the updated branch's id
             "updater": integer, // the id of the user that caused the update
             "from_head": integer, // the id of the branch's head before the update
             "to_head": integer, // the id of the branch's head after the update
             "associated": [integer], // the id of each newly associated commit
             "disassociated": [integer], // the id of each newly disassociated commit
             "timestamp": float,
             "output": string, // Git hook output
           }"""

        associated_commits = list(value.associated_commits.topo_ordered)
        disassociated_commits = list(value.disassociated_commits.topo_ordered)

        return parameters.filtered(
            "branchupdates",
            { "id": value.id,
              "branch": value.branch,
              "updater": value.updater,
              "from_head": value.from_head,
              "to_head": value.to_head,
              "associated": associated_commits,
              "disassociated": disassociated_commits,
              "timestamp": jsonapi.v1.timestamp(value.timestamp),
              "output": value.output })

    @staticmethod
    def single(parameters, argument):
        """Retrieve one (or more) branch updates.

           BRANCHUPDATE_ID : integer

           Retrieve a branch update identified by its unique numeric id."""

        branchupdate = api.branchupdate.fetch(
            parameters.critic, branchupdate_id=jsonapi.numeric_id(argument))
        branch = jsonapi.deduce("v1/branches", parameters)

        if branch and branch != branchupdate.branch:
            raise jsonapi.PathError(
                "Branch update is not of the specified branch")

        return branchupdate

    @staticmethod
    def multiple(parameters):
        """Retrieve all updates of a particular branch.

           branch : BRANCH_ID : integer

           The branch whose updates to retrieve, identified by the branch's
           unique numeric id."""

        branch = jsonapi.deduce("v1/branches", parameters)

        return api.branchupdate.fetchAll(branch)
