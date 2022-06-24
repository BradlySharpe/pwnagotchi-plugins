# Heavily based on Switcher and WebConfig Plugins

import os
import logging
import json
from pwnagotchi import plugins
from pwnagotchi import reboot
from flask import abort
from flask import render_template_string

def systemctl(command, unit=None):
    if unit:
        os.system("/bin/systemctl %s %s" % (command, unit))
    else:
        os.system("/bin/systemctl %s" % command)

def systemd_dropin(name, content):
    if not name.endswith('.service'):
        name = '%s.service' % name

    dropin_dir = "/etc/systemd/system/%s.d/" % name
    os.makedirs(dropin_dir, exist_ok=True)

    with open(os.path.join(dropin_dir, "enterprise.conf"), "wt") as dropin:
        dropin.write(content)

    systemctl("daemon-reload")

def create_service(task_service_name):
    # here we create the service which runs the tasks
    with open('/etc/systemd/system/%s' % task_service_name, 'wt') as task_service:
        task_service.write("""
        [Unit]
        Description=Executes the tasks of the pwnagotchi enterprise plugin
        After=pwnagotchi.service bettercap.service

        [Service]
        Type=oneshot
        RemainAfterExit=yes
        ExecStart=-/usr/local/bin/enterprise.sh
        ExecStart=-/bin/rm /etc/systemd/system/%s
        ExecStart=-/bin/rm /usr/local/bin/enterprise.sh

        [Install]
        WantedBy=multi-user.target
        """ % (task_service_name))

def create_reboot_timer(timeout):
    with open('/etc/systemd/system/enterprise-reboot.timer', 'wt') as reboot_timer:
        reboot_timer.write("""
        [Unit]
        Description=Reboot when time is up
        ConditionPathExists=/root/.enterprise

        [Timer]
        OnBootSec=%sm
        Unit=reboot.target

        [Install]
        WantedBy=timers.target
        """ % timeout)

def create_command(script_path, commands):
    with open(script_path, 'wt') as script_file:
        script_file.write('#!/bin/bash\n')
        for cmd in commands:
            script_file.write('%s\n' % cmd)

def add_task(options):
    task_service_name = "enterprise-task.service"

    # save all the commands to a shell script
    script_dir = '/usr/local/bin/'
    script_path = os.path.join(script_dir, 'enterprise.sh')
    os.makedirs(script_dir, exist_ok=True)

    create_command(script_path, options['commands'])

    os.system("chmod a+x %s" % script_path)

    create_service(task_service_name)

    # create a indication file!
    # if this file is set, we want the enterprise-tasks to run
    open('/root/.enterprise', 'a').close()

    # add condition
    systemd_dropin("pwnagotchi.service", """
    [Unit]
    ConditionPathExists=!/root/.enterprise""")

    systemd_dropin("bettercap.service", """
    [Unit]
    ConditionPathExists=!/root/.enterprise""")

    systemd_dropin(task_service_name, """
    [Service]
    ExecStart=-/bin/rm /root/.enterprise
    ExecStart=-/bin/rm /etc/systemd/system/enterprise-reboot.timer""")

    create_reboot_timer(options['timeout'])

    systemctl("daemon-reload")
    systemctl("enable", "enterprise-reboot.timer")
    systemctl("enable", task_service_name)
    reboot()

# def serializer(obj):
#     if isinstance(obj, set):
#         return list(obj)
#     raise TypeError

class Enterprise(plugins.Plugin):
    __author__ = '5461464+BradlySharpe@users.noreply.github.com'
    __version__ = '0.0.1'
    __name__ = 'enterprise'
    __license__ = 'GPL3'
    __description__ = 'This plugin will attempt to obtain credentials from enterprise networks when bored and networks are available.'

    def __init__(self):
        self.config = {
            "ssid": "",
            "bssid": "",
            "channel": 0,
            "duration": 2, # minutes
            "enabled": False,
            "access_points": []
        }
        self.rebooting = False
        self.ready = False
    
    def on_ready(self, agent):
        self.ready = True
        logging.info("[enterprise] unit is ready")

    # called when the agent refreshed its access points list
    def on_wifi_update(self, agent, access_points):
        if not self.ready:
            return

        logging.debug("[enterprise] wifi update", access_points)
        self.access_points = access_points

    def trigger(self):
        if not self.ready:
            return

        if self.config["enabled"]:
            self.rebooting = True
            
            add_task(self.config)
        
    # called when the status is set to bored
    def on_bored(self, agent):
       self.trigger()

    # called when the status is set to sad
    def on_sad(self, agent):
       self.trigger()

    def on_loaded(self):
        logging.info("[enterprise] is loaded.")

    def on_ui_update(self, ui):
        if self.rebooting:
            ui.set('line1', "Off to capture WPA-E Creds")
            ui.set('line2', "SSID: %s" % self.config["ssid"])


    def on_webhook(self, path, request):
        """
        Serves the current configuration
        """
        if not self.ready:
            return "Plugin not ready"

        if request.method == "GET":
            if path == "/" or not path:
                return render_template_string(INDEX)
            elif path == "get-config":
                return json.dumps(self.config) #, default=serializer)
            else:
                abort(404)
        elif request.method == "POST":
            if path == "update-task":
                try:
                    # Update configuration here
                    return "success"
                except Exception as ex:
                    logging.error(ex)
                    return "config error", 500
        abort(404)

INDEX = """
{% extends "base.html" %}
{% set active_page = "plugins" %}
{% block title %}
    Enterprise
{% endblock %}

{% block meta %}
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, user-scalable=0" />
{% endblock %}

{% block styles %}
{{ super() }}
<style>
    /*
    #divTop {
        position: -webkit-sticky;
        position: sticky;
        top: 0px;
        width: 100%;
        font-size: 16px;
        padding: 5px;
        border: 1px solid #ddd;
        margin-bottom: 5px;
    }
    */

    #btnSave {
        position: -webkit-sticky;
        position: sticky;
        bottom: 0px;
        width: 100%;
        background-color: #0061b0;
        border: none;
        color: white;
        padding: 15px 32px;
        text-align: center;
        text-decoration: none;
        display: inline-block;
        font-size: 16px;
        cursor: pointer;
        float: right;
    }

    #divTop {
        display: table;
        width: 100%;
    }
    #divTop > * {
        display: table-cell;
    }
    /*
    #divTop > span {
        width: 1%;
    }
    */
    #divTop > input {
        width: 100%;
    }

    @media screen and (max-width:700px) {
        
    }
</style>
{% endblock %}

{% block content %}
    <div id="divTop">
    </div>
    <button id="btnSave" type="button" onclick="saveConfig()">Save and restart</button>
    <hr />
    <h4>Access Points</h4>
    <div id="content"></div>
{% endblock %}

{% block script %}
        function saveConfig(){
            var json = {};
            sendJSON("enterprise/update-task", json, function(response) {
                if (response) {
                    if (response.status == "200") {
                        alert("Task updated");
                    } else {
                        alert("Error while updating the task (err-code: " + response.status + ")");
                    }
                }
            });
        }
        
        function sendJSON(url, data, callback) {
          var xobj = new XMLHttpRequest();
          var csrf = "{{ csrf_token() }}";
          xobj.open('POST', url);
          xobj.setRequestHeader("Content-Type", "application/json");
          xobj.setRequestHeader('x-csrf-token', csrf);
          xobj.onreadystatechange = function () {
                if (xobj.readyState == 4) {
                  callback(xobj);
                }
          };
          xobj.send(JSON.stringify(data));
        }

        function loadJSON(url, callback) {
          var xobj = new XMLHttpRequest();
          xobj.overrideMimeType("application/json");
          xobj.open('GET', url, true);
          xobj.onreadystatechange = function () {
                if (xobj.readyState == 4 && xobj.status == "200") {
                  callback(JSON.parse(xobj.responseText));
                }
          };
          xobj.send(null);
        }

        loadJSON("enterprise/get-config", function(response) {
            var divContent = document.getElementById("content");
            divContent.innerHTML = "";
            divContent.innerHTML = response;
            //divContent.appendChild(table);
        });
{% endblock %}
"""
