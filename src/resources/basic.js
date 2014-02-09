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

/* -*- Mode: js; js-indent-level: 2; indent-tabs-mode: nil -*- */

function User(id, name, email, displayName, status, options)
{
  this.id = id;
  this.name = name;
  this.email = email;
  this.displayName = displayName;
  this.status = status;
  this.options = options || {};
}

User.prototype.toString = function () { return this.displayName + " <" + this.email + ">"; };

function Repository(id, name, path)
{
  this.id = id;
  this.name = name;
  this.path = path;
}

function Branch(id, name, base)
{
  this.id = id;
  this.name = name;
  this.base = base;
}

function reportError(what, specifics, title, callback)
{
  if (!title)
    title = "Communication Error!";

  var content = $("<div class=error-dialog title='" + title + "'><h1>Failed to " + what + ".</h1><p>" + specifics + "</p></div>");

  content.dialog({ width: 800,
                   height: 400,
                   modal: true,
                   buttons: { OK: function () { content.dialog("close"); if (callback) callback(); }}});
}

function showMessage(title, heading, message, callback)
{
  var content = $("<div class=message-dialog title='" + title + "'><h1>" + heading + "</h1>" + (message || "") + "</div>");

  content.dialog({ width: 600, modal: true, buttons: { OK: function () { content.dialog("close"); if (callback) callback(); }}});
}

function htmlify(text, attribute)
{
  text = String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;");
  if (attribute)
    text = text.replace(/'/g, "&apos;").replace(/"/g, "&quot;");
  return text;
}

function Operation(data)
{
  this.action = data.action;
  this.url = data.url;
  this.data = data.data;
  this.wait = data.wait;
  this.cancelable = data.cancelable;
  this.failure = data.failure || {};
  this.callback = data.callback;
  this.id = ++Operation.counter;

  if (this.callback)
    Operation.current[this.id] = true;
}

Operation.SUPPORTS_CALLBACK = true;
Operation.current = {};
Operation.counter = 0;
Operation.idleCallbacks = [];

Operation.isBusy = function ()
  {
    return Object.keys(Operation.current).length != 0;
  };

Operation.whenIdle = function (callback)
  {
    if (Operation.isBusy())
      Operation.idleCallbacks.push(callback);
    else
      callback();
  };

Operation.finished = function (id)
  {
    delete Operation.current[id];
  };

Operation.checkIdle = function ()
  {
    if (!Operation.isBusy())
    {
      Operation.idleCallbacks.forEach(function (fn) { fn(); });
      Operation.idleCallbacks = [];
    }
  };

window.addEventListener("beforeunload", function (ev)
                        {
                          if (Operation.isBusy())
                          {
                            ev.returnValue = "There are pending requests to the server.  You probably want to let them finish before you leave the page.";
                            ev.preventDefault();
                          }
                        });

Operation.prototype.execute = function ()
  {
    var self = this;
    var result = null;
    var wait = null;

    function handleResult(result, callback)
    {
      callback = callback || function (result) { return result; };

      if (result.status == "failure")
      {
        var handler = self.failure[result.code];

        if (!handler || !handler(result))
          showMessage("Oups...", result.title, result.message, function () { callback(null); });

        return null;
      }
      else if (result.status == "error")
      {
        if (result.error.indexOf("\n") != -1)
          reportError(self.action, "Server reply:<pre>" + htmlify(result.error) + "</pre>", null, function () { callback(null); });
        else
          reportError(self.action, "Server reply: <i>" + htmlify(result.error) + "</i>", null, function () { callback(null); });

        return null;
      }
      else
        return callback(result);
    }

    function success(data)
    {
      self.ajax = null;
      result = data;
      if (data.__profiling__)
        console.log(self.url + "\n" +
                    Array(self.url.length + 1).join("=") + "\n" +
                    "Total: " + data.__time__.toPrecision(3) + " seconds\n" +
                    data.__profiling__);
      if (wait)
        wait.dialog("close");
      if (self.callback)
      {
        Operation.finished(self.id);
        handleResult(result, self.callback);
        Operation.checkIdle();
      }
    }

    function error(xhr)
    {
      self.ajax = null;
      if (wait)
        wait.dialog("close");
      if (!self.aborted)
      {
        if (xhr.status == 404)
          reportError(self.action,
                      "<p>The operation <code>" + self.url + "</code> is not supported by the server.<p>" +
                      "<p>Simply reloading the page and then trying again might help.  " +
                      "If that doesn't help, and you think an extension might be " +
                      "involved, try reinstalling (or uninstalling) it.</p>",
                      null, self.callback);
        else
          reportError(self.action, "Server reply:<pre>" + (xhr.responseText ? htmlify(xhr.responseText) : "N/A") + "</pre>", null, self.callback);
        if (self.callback)
          Operation.finished(self.id);
      }
    }

    if (this.wait)
    {
      wait = $("<div title='Please Wait' style='text-align: center; padding-top: 2em'>" + this.wait + "</div>");
      var data = { modal: true };
      if (this.cancelable)
        data.buttons = { "Cancel": function () { wait.dialog("close"); self.ajax.abort(); }};
      wait.dialog(data);
    }

    this.ajax = $.ajax({ async: !!this.callback,
                         type: "POST",
                         url: "/" + this.url,
                         contentType: "text/json",
                         data: JSON.stringify(this.data),
                         dataType: "json",
                         success: success,
                         error: error });

    if (!this.callback)
    {
      if (wait)
        wait.dialog("close");

      if (result)
        return handleResult(result);
      else
        return null;
    }
  };

Operation.prototype.abort = function ()
  {
    this.aborted = true;
    if (this.ajax)
      this.ajax.abort();
  };

$(document).ready(function ()
  {
    $("button").button();
    $("a.button").button();
  });

var keyboardShortcutHandlers = [];

function handleKeyboardShortcut(key)
{
  for (var index = 0; index < keyboardShortcutHandlers.length; ++index)
    if (keyboardShortcutHandlers[index](key))
      return true;
  return false;
}

$(document).ready(function ()
  {
    if (typeof keyboardShortcuts == "undefined" || keyboardShortcuts)
      $(document).keypress(function (ev)
        {
          if (ev.ctrlKey || ev.shiftKey || ev.altKey || ev.metaKey)
            return;

          if (/^(?:input|textarea)$/i.test(ev.target.nodeName))
            if (ev.which == 32 || /textarea/i.test(ev.target.nodeName) || !/^(?:checkbox|radio)$/i.test(ev.target.type))
              return;

          /* Handling non-printable keys. */
          if (ev.which)
          {
            if (handleKeyboardShortcut(ev.which))
              ev.preventDefault();
          }
        });
  });

if (!Object.create)
{
  Object.create =
    function (proto, props)
    {
      var object = {};

      try { object.__proto__ = proto; }
      catch (e) {}

      for (var name in props)
      {
        if ("value" in props[name])
          object[name] = props[name].value;
        else
        {
          if (props[name].get)
            object.__defineGetter__(name, props[name].get);
          if (props[name].set)
            object.__defineSetter__(name, props[name].set);
        }
      }

      return object;
    };
}

var hooks = Object.create(null, {
  "create-comment": { value: [] },
  "display-comment": { value: [] }
});

var critic = {
  Operation: Operation,

  buttons: {
    add: function (data)
      {
        if (!data.title || !(data.href || data.onclick) || !data.scope)
          throw new TypeError("invalid data; should have 'title', 'scope' and 'href'/'onclick' properties");

        if (data.href)
          html = "<a href='" + htmlify(data.href, true) + "'>" + htmlify(data.title) + "</a>";
        else if (typeof data.onclick == "function")
          html = "<button>" + htmlify(data.title) + "</button>";
        else
          html = "<button onclick='" + htmlify(data.onclick, true) + "'>" + htmlify(data.title) + "</button>";

        var button = $(html);

        if (typeof data.onclick == "function")
          button.click(data.onclick);

        button.button();

        $("span.buttonscope-" + data.scope).append(button);
      },

    remove: function (data)
      {
        if (!data.title || !data.scope)
          throw new TypeError("invalid data; should have 'title' and 'scope' properties");

        $("span.buttonscope-" + data.scope + " button").filter(function () { return $(this).text() == data.title }).detach();
      }
  },

  hooks: {
    add: function (name, callback)
      {
        if (!(name in hooks))
          throw new TypeError("invalid hook; valid alternatives are: " + Object.keys(hooks));

        hooks[name].push(callback);
      }
  },

  html: {
    escape: htmlify
  }
};

function signOut()
{
  var operation = new Operation({ action: "sign out",
                                  url: "endsession",
                                  data: {}});

  if (operation.execute())
    location.href = "/";
}

function repositionNotifications()
{
  $("body > div.notifications").position({ my: "center top",
                                           at: "center top",
                                           of: window });
}

function showNotification(content, data)
{
  data = data || {};

  var notifications = $("body > div.notifications");

  if (notifications.size() == 0)
  {
    notifications = $("<div class=notifications></div>");
    $("body").append(notifications);
    repositionNotifications();
  }

  var notification = $("<div class=notification></div>");

  function displayed()
  {
    setTimeout(hide, (data.duration || 3) * 1000);
  }

  function hide()
  {
    if (notification.next("div.notification").size())
      remove();
    else
    {
      /* Using .animate({ opacity: 0 }) instead of .fadeOut() since the latter
         "helpfully" sets display:none at the end of the animation.  We want to
         also do .slideUp(), and that only works if the element is still there. */
      notification.animate(
        { opacity: 0 }, { duration: 600, complete: remove });
    }
  }

  function remove()
  {
    if (data.callback)
      data.callback();

    notification.slideUp(400, finalize);
  }

  function finalize()
  {
    notification.remove();
  }

  if (data.className)
    notification.addClass(data.className);

  notification.append(content);
  notification.fadeIn(400, displayed);
  notification.click(hide);

  notifications.append(notification);

  return { hide: hide, remove: remove };
}

var previous_query = "";

if (typeof localStorage != "undefined")
  previous_query = localStorage.getItem("previous_query");

function quickSearch(external_query, callback)
{
  function finish(result)
  {
    if (!result)
    {
      if (external_query === void 0)
        setTimeout(quickSearch, 0);
      return;
    }

    if (result.reviews.length == 0)
    {
      showMessage("Search results", "No reviews found!");
      return;
    }

    var html = ("<table class=searchresults>" +
                "<tr><th class=id>Review</th><th class=summary>Summary</th>");

    html += "</tr>";

    result.reviews.forEach(function (review, index)
      {
        html += ("<tr class=review critic-review-id=" + review.id + ">" +
                 "<td class=id>r/" + review.id + "</td>" +
                 "<td class=summary><a href=/r/" + review.id + ">" + htmlify(review.summary) + "</a></td>" +
                 "</tr>");
      });

    html += "</table></div>";

    var content = $(html);

    content.find("tr").click(function (ev)
      {
        var target = $(ev.target);
        if (!target.is("a"))
          target.parents("tr").find("a").get(0).click();
      });

    if (callback)
      callback(content, result);
    else
    {
      content.wrap("<div title='Search results'></div>");
      content.find("tr").first().append(
        "<td class=link><a>Link to this search</a></td>");
      content.find("td.link a").attr("href", "/search?" + result.query_string);
      content.find("td.summary").attr("colspan", "2");

      content = content.parent();
      content.dialog(
        { width: 800,
          buttons: { "Close": function () { content.dialog("close"); }}});

      if (content.closest(".ui-dialog").height() > innerHeight)
        content.dialog("option", "height", innerHeight - 10);
    }
  }

  function search(query)
  {
    var operation = new Operation({ action: "search",
                                    url: "searchreview",
                                    data: { query: query },
                                    wait: "Searching...",
                                    callback: finish });

    operation.execute();
  }

  if (external_query !== void 0)
  {
    search(external_query);
    return;
  }

  function start()
  {
    previous_query = content.find("input").val().trim();

    if (typeof localStorage != "undefined")
      localStorage.setItem("previous_query", previous_query);

    content.dialog("close");

    if (previous_query)
      search(previous_query);
  }

  function cancel()
  {
    content.dialog("close");
  }

  function handleKeypress(ev)
  {
    if (ev.keyCode == 13)
      start();
  }

  var content = $("<div title='Review Quick Search' class=searchdialog>" +
                  "<div><b>Search query:</b>" +
                  "<span class=help><a href=/tutorial?item=search>Help</a></span></div>" +
                  "<div><input></div>" +
                  "</div>");

  content.find("input")
    .val(previous_query)
    .keypress(handleKeypress);

  content.dialog({ width: 800,
                   buttons: { "Search": start, "Cancel": cancel }});

  setTimeout(function () { content.find("input").select(); content.find("input").focus(); }, 0);
}

keyboardShortcutHandlers.push(function (key)
  {
    if (key == "f".charCodeAt(0))
    {
      quickSearch();
      return true;
    }
  });

$(window).resize(repositionNotifications);
