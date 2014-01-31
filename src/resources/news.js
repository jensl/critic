/* -*- mode: js; indent-tabs-mode: nil -*-

 Copyright 2012 Jens Lindström, Opera Software ASA

 Licensed under the Apache License, Version 2.0 (the "License"); you may not
 use this file except in compliance with the License.  You may obtain a copy of
 the License at

   http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
 License for the specific language governing permissions and limitations under
 the License.

*/

function addOrEditNewsItem(edit_item_id, edit_text)
{
  function finish()
  {
    var text = content.find("textarea").val();
    var operation;

    if (edit_item_id)
      operation = new Operation({ action: "edit news item",
                                  url: "editnewsitem",
                                  data: { item_id: edit_item_id,
                                          text: text }});
    else
      operation = new Operation({ action: "add news item",
                                  url: "addnewsitem",
                                  data: { text: text }});

    return !!operation.execute();
  }

  var verb = edit_item_id ? "Edit" : "Create"

  var content = $("<div class='comment flex' title='" + verb + " News Item'>" +
                  "<textarea class='text flexible' rows=8></textarea></div>");

  if (edit_text)
    content.find("textarea").val(edit_text);

  var buttons = { Save: function () { if (finish()) { $(content).dialog("close"); location.reload(); } },
                  Cancel: function () { $(content).dialog("close"); } };

  content.dialog({ width: 600,
                   buttons: buttons,
                   closeOnEscape: false });
}

$(document).ready(function ()
  {
    $("button, a.show, a.back").button();
    $("button.addnewsitem").click(function () { addOrEditNewsItem(false); });
    $("button.editnewsitem").click(function () { addOrEditNewsItem(news_item_id, news_text); });
    $("tr.item").click(function (ev)
      {
        var target = $(ev.currentTarget);
        location.search = "item=" + target.attr("critic-item-id");
      });
  });
