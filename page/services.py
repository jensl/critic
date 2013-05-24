# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2012 Jens Lindström, Opera Software ASA
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

import os
import os.path
import socket
import time
import errno

import page.utils
import htmlutils
import dbutils
import configuration
import textutils

def renderServices(req, db, user):
    req.content_type = "text/html; charset=utf-8"

    document = htmlutils.Document(req)
    document.setTitle("Services")

    html = document.html()
    head = html.head()
    body = html.body()

    page.utils.generateHeader(body, db, user, current_page="services")

    document.addExternalStylesheet("resource/services.css")
    document.addExternalScript("resource/services.js")
    document.addInternalScript(user.getJS())

    delay = 0.5
    connected = False

    while not connected and delay <= 10:
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        # This loop is for the case where we just restarted the service manager
        # via the /services UI.  The client-side script immediately reloads the
        # page after restart, which typically leads to us trying to connect to
        # the service manager while it's in the process of restarting.  So just
        # try a couple of times if at first the connection fails.

        try:
            connection.connect(configuration.services.SERVICEMANAGER["address"])
            connected = True
        except socket.error, error:
            if error[0] in (errno.ENOENT, errno.ECONNREFUSED):
                time.sleep(delay)
                delay += delay
            else: raise

    if not connected:
        raise page.utils.DisplayMessage, "Service manager not responding!"

    connection.send(textutils.json_encode({ "query": "status" }))
    connection.shutdown(socket.SHUT_WR)

    data = ""
    while True:
        received = connection.recv(4096)
        if not received: break
        data += received

    result = textutils.json_decode(data)

    if result["status"] == "error":
        raise page.utils.DisplayMessage, result["error"]

    paleyellow = page.utils.PaleYellowTable(body, "Services")

    def render(target):
        table = target.table("services", cellspacing=0, align="center")

        headings = table.tr("headings")
        headings.th("name").text("Name")
        headings.th("module").text("Module")
        headings.th("pid").text("PID")
        headings.th("rss").text("RSS")
        headings.th("cpu").text("CPU")
        headings.th("uptime").text("Uptime")
        headings.th("commands").text()

        table.tr("spacer").td("spacer", colspan=4)

        def formatUptime(seconds):
            def inner(seconds):
                if seconds < 60: return "%d seconds" % seconds
                elif seconds < 60 * 60: return "%d minutes" % (seconds / 60)
                elif seconds < 60 * 60 * 24: return "%d hours" % (seconds / (60 * 60))
                else: return "%d days" % (seconds / (60 * 60 * 24))
            return inner(int(seconds)).replace(" ", "&nbsp;")

        def formatRSS(bytes):
            if bytes < 1024: return "%d B" % bytes
            elif bytes < 1024 ** 2: return "%.1f kB" % (float(bytes) / 1024)
            elif bytes < 1024 ** 3: return "%.1f MB" % (float(bytes) / 1024 ** 2)
            else: return "%.1f GB" % (float(bytes) / 1024 ** 3)

        def formatCPU(seconds):
            minutes = int(seconds / 60)
            seconds = seconds - minutes * 60
            seconds = "%2.2f" % seconds
            if seconds.find(".") == 1: seconds = "0" + seconds
            return "%d:%s" % (minutes, seconds)

        def getProcessData(pid):
            try:
                items = open("/proc/%d/stat" % pid).read().split()

                return { "cpu": formatCPU(float(int(items[13]) + int(items[14])) / os.sysconf("SC_CLK_TCK")),
                         "rss": formatRSS(int(items[23]) * os.sysconf("SC_PAGE_SIZE")) }
            except:
                return { "cpu": "N/A",
                         "rss": "N/A" }

        for service_name, service_data in sorted(result["services"].items()):
            process_data = getProcessData(service_data["pid"])

            row = table.tr("service")
            row.td("name").text(service_name)
            row.td("module").text(service_data["module"])
            row.td("pid").text(service_data["pid"] if service_data["pid"] != -1 else "(not running)")
            row.td("rss").text(process_data["rss"])
            row.td("cpu").text(process_data["cpu"])
            row.td("uptime").innerHTML(formatUptime(service_data["uptime"]))

            commands = row.td("commands")
            commands.a(href="javascript:void(restartService(%s));" % htmlutils.jsify(service_name)).text("[restart]")
            commands.a(href="javascript:void(getServiceLog(%s));" % htmlutils.jsify(service_name)).text("[log]")

        for index, pid in enumerate(os.listdir(configuration.paths.WSGI_PIDFILE_DIR)):
            startup = float(open(os.path.join(configuration.paths.WSGI_PIDFILE_DIR, pid)).read())
            uptime = time.time() - startup

            process_data = getProcessData(int(pid))

            row = table.tr("service")
            row.td("name").text("wsgi:%d" % index)
            row.td("module").text()
            row.td("pid").text(pid)
            row.td("rss").text(process_data["rss"])
            row.td("cpu").text(process_data["cpu"])
            row.td("uptime").innerHTML(formatUptime(uptime))

            commands = row.td("commands")
            commands.a(href="javascript:void(restartService('wsgi'));").text("[restart]")

    paleyellow.addCentered(render)

    return document
