# Copyright 2018-2019, domcross
# Github https://github.com/domcross
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# from adapt.intent import IntentBuilder
from mycroft import intent_handler, AdaptIntent, intent_file_handler
from mycroft.api import DeviceApi
from mycroft.skills.core import FallbackSkill
from mycroft.util.log import LOG
#from mycroft.util.parse import match_one

# from os.path import dirname, join
from rapidfuzz import fuzz
import re
import fhem as python_fhem

__author__ = 'domcross'

REQUIRED_RATIO_FOR_BONUS = 89
BONUS = 25


class FhemSkill(FallbackSkill):

    def __init__(self):
        super(FhemSkill, self).__init__(name="FhemSkill")
        LOG.info("__init__")
        self.fhem = None
        self.enable_fallback = False
        self.device_location = ""

    def _setup(self, force=False):
        # when description of home.mycroft.ai > Devices > [this mycroft device]
        # is filled, use this the name of the room where mycroft is located
        if self.settings.get('device_location', False):
            dev = DeviceApi()
            info = dev.get()
            if 'description' in info:
                self.device_location = info['description']
        LOG.debug("mycroft device location: {}".format(self.device_location))

        if self.settings and (force or self.fhem is None):
            LOG.debug("_setup")
            portnumber = self.settings.get('portnum')
            try:
                portnumber = int(portnumber)
            except TypeError:
                portnumber = 8083
            except ValueError:
                # String might be some rubbish (like '')
                portnumber = 0

            self.fhem = \
                python_fhem.Fhem(self.settings.get('host'),
                                 port=portnumber,  csrf=True,
                                 protocol=self.settings.get('protocol',
                                                            'http').lower(),
                                 use_ssl=self.settings.get('ssl', False),
                                 username=self.settings.get('username'),
                                 password=self.settings.get('password')
                                 )
            self.fhem.connect()
            LOG.debug("connect: {}".format(self.fhem.connected()))
            if self.fhem.connected():
                self.allowed_devices_room = self.settings.get('room', 'Homebridge')
                self.ignore_rooms = self.settings.get('ignore_rooms', '')

                # Check if natural language control is loaded at fhem-server
                # and activate fallback accordingly
                LOG.debug("fallback_device_name %s" %
                          self.settings.get('fallback_device_name'))
                LOG.debug("enable_fallback %s" %
                          self.settings.get('enable_fallback'))
                if self.settings.get('enable_fallback') and \
                   self.settings.get('fallback_device_name', ""):
                    fallback_device = \
                        self.fhem.get_device(self.settings.get(
                            'fallback_device_name', ""))
                    if fallback_device:
                        # LOG.debug("fallback device {}".format(fallback_device))
                        self.fallback_device_name = self.settings.get(
                            'fallback_device_name', "")
                        self.fallback_device_type = self.fhem.get_internals(
                            "TYPE", name=self.fallback_device_name)[
                                self.fallback_device_name]
                        LOG.debug("fallback_device_type is %s" %
                                  self.fallback_device_type)
                        if self.fallback_device_type in ["Talk2Fhem",
                                                         "TEERKO",
                                                         "Babble"]:
                            self.enable_fallback = True
                        else:
                            self.enable_fallback = False
                else:
                    self.enable_fallback = False
                LOG.debug('fhem-fallback enabled: %s' % self.enable_fallback)

    def initialize(self):
        self._setup(True)
        # Needs higher priority than general fallback skills
        self.register_fallback(self.handle_fallback, 2)
        # Check and then monitor for credential changes
        self.settings_change_callback = self.on_websettings_changed

        # registering entities, is that actually necessary?
        self.register_entity_file('action.entity')
        self.register_entity_file('room.entity')
        self.register_entity_file('open.entity')
        self.register_entity_file('close.entity')
        #self.register_entity_file('blind.entity')

    def on_websettings_changed(self):
        # Only attempt to load if the host is set
        LOG.debug("websettings changed")
        if self.settings.get('host', None):
            try:
                self._setup(force=True)
            except Exception:
                pass

    #@intent_file_handler('blind.intent')
    def handle_blind_intent(self, message):
        self._setup()
        if self.fhem is None:
            self.speak_dialog('fhem.error.setup')
            return
        LOG.info("Starting Blind Intent")
        LOG.info("message.data {}".format(message.data))

        device = message.data.get("device")
        action = ""
        percent = None
        if message.data.get("open"):
            action = "open"
            speak_action = message.data.get("open")
            target_pct = 0
        elif message.data.get("close"):
            action = "closed" # sic!
            speak_action = message.data.get("close")
            target_pct = 100
        elif message.data.get("percent"):
            percent = message.data.get("percent")
            if percent.isdigit():
                action = "pct"
                target_pct = int(percent)

        if not action:
            LOG.info("no action for blind intent found!")
            return False
        if message.data.get("room"):
            room = message.data.get("room")
        else:
            # if no room is given use device location
            room = self.device_location
        allowed_types = 'blind'
        LOG.info("Device: %s" % device)
        LOG.info("Action: %s" % action)
        LOG.info("Room: %s" % room)
        if percent:
            LOG.info("Percent: %s" % percent)
        try:
            fhem_device = self._find_device(device, allowed_types, room)
        except ConnectionError:
            self.speak_dialog('fhem.error.offline')
            return
        if fhem_device is None:
            self.speak_dialog('fhem.device.unknown', data={"dev_name": device})
            return
        LOG.info("Entity State: %s" % fhem_device['state'])

        open_pct = 0
        closed_pct = 100

        blind = self.fhem.get_device(fhem_device['id'])[0]
        if blind['Internals']['TYPE'] == 'ROLLO':
            if action == "pct":
                self.fhem.send_cmd("set {} pct {}".format(fhem_device['id'],
                                                          target_pct))
                self.speak_dialog('fhem.blind.set',
                                  data={"device": device,
                                        "percent": target_pct})
            else:
                self.fhem.send_cmd("set {} {}".format(fhem_device['id'],
                                                      action))
                self.speak_dialog('fhem.blind', data={"device": device,
                                                      "action": speak_action,
                                                      "room": room})
        else:
            self.speak_dialog('fhem.error.notsupported')
            return

    @intent_file_handler('switch.intent')
    def handle_switch_intent(self, message):
        self._setup()
        if self.fhem is None:
            self.speak_dialog('fhem.error.setup')
            return
        LOG.debug("Starting Switch Intent")
        LOG.debug("message.data {}".format(message.data))

        device = message.data.get("device")
        if message.data.get("action"):
            action = message.data.get("action")
            self.log.info("action: {}".format(action))
        else:
            # when no action is given toggle the device
            action = "toggle"
        if message.data.get("room"):
            room = message.data.get("room")
        else:
            # if no room is given use device location
            room = self.device_location
        allowed_types = '(light|switch|outlet)'
        LOG.debug("Device: %s" % device)
        LOG.debug("Action: %s" % action)
        LOG.debug("Room: %s" % room)

        # TODO if entity is 'all', 'any' or 'every' turn on
        # every single entity not the whole group
        try:
            fhem_device = self._find_device(device, allowed_types, room)
        except ConnectionError:
            self.speak_dialog('fhem.error.offline')
            return
        if fhem_device is None:
            self.speak_dialog('fhem.device.unknown', data={"dev_name": device})
            return
        LOG.debug("Entity State: %s" % fhem_device['state'])
        # fhem_data = {'entity_id': fhem_entity['id']}

        # keep original actioname for speak_dialog
        # when device already is in desiredstate
        if action != 'toggle':
            original_action = action
        else:
            original_action = self.translate('toggle_keyword')
        action_values = self.translate_namedvalues('actions.value')
        if action in action_values.keys():
            action = action_values[action]
        LOG.debug("- action: %s" % action)
        LOG.debug("- state: %s" % fhem_device['state']['Value'])
        if fhem_device['state']['Value'] == action:
            LOG.debug("Entity in requested state")
            self.speak_dialog('fhem.device.already', data={
                'dev_name': fhem_device['dev_name'],
                'action': original_action})
        elif action == 'toggle':
            if(fhem_device['state']['Value'] == 'off'):
                action = 'on'
            else:
                action = 'off'
            LOG.debug("toggled action: %s" % action)
            self.fhem.send_cmd("set {} {}".format(fhem_device['id'], action))
            self.speak_dialog('fhem.switch',
                              data={'dev_name': fhem_device['dev_name'],
                                    'action': original_action})
        elif action in ["on", "off"]:
            LOG.debug("action: on/off")
            self.speak_dialog('fhem.switch',
                              data={'dev_name': fhem_device['dev_name'],
                                    'action': original_action})
            self.fhem.send_cmd("set {} {}".format(fhem_device['id'], action))
        else:
            self.speak_dialog('fhem.error.sorry')
            return

    @intent_handler(AdaptIntent().optionally("LightsKeyword")
                    .require("SetVerb").require("Device")
                    .require("BrightnessValue"))
    def handle_light_set_intent(self, message):
        # TODO not supported yet
        self.speak_dialog('fhem.error.notsupported')
        return
        #
        self._setup()
        if(self.fhem is None):
            self.speak_dialog('fhem.error.setup')
            return
        device = message.data["Device"]
        allowed_types = ['light']  # TODO
        try:
            brightness_req = float(message.data["BrightnessValue"])
            if brightness_req > 100 or brightness_req < 0:
                self.speak_dialog('fhem.brightness.badreq')
        except KeyError:
            brightness_req = 10.0
        brightness_value = int(brightness_req / 100 * 255)
        brightness_percentage = int(brightness_req)
        LOG.debug("device: %s" % device)
        LOG.debug("Brightness Value: %s" % brightness_value)
        LOG.debug("Brightness Percent: %s" % brightness_percentage)
        try:
            fhem_device = self.fhem.find_device(device, allowed_types)
        except ConnectionError:
            self.speak_dialog('fhem.error.offline')
            return
        if fhem_device is None:
            self.speak_dialog('fhem.device.unknown', data={
                              "dev_name": device})
            return
        fhem_data = {'device_id': fhem_device['id']}

        # IDEA: set context for 'turn it off again' or similar
        # self.set_context('Entity', fhem_entity['dev_name'])

        # TODO - Allow value set
        if "SetVerb" in message.data:
            fhem_data['brightness'] = brightness_value
            fhem_data['dev_name'] = fhem_device['dev_name']
            self.fhem.execute_service("fhem", "turn_on", fhem_data)
            self.speak_dialog('fhem.brightness.dimmed',
                              data=fhem_data)
        else:
            self.speak_dialog('fhem.error.sorry')
            return

    @intent_handler(AdaptIntent().optionally("LightsKeyword")
                    .one_of("IncreaseVerb", "DecreaseVerb",
                            "LightBrightenVerb", "LightDimVerb")
                    .require("Device").optionally("BrightnessValue"))
    def handle_light_adjust_intent(self, message):
        # TODO not supported yet
        self.speak_dialog('fhem.error.notsupported')
        return
        #
        self._setup()
        if self.fhem is None:
            self.speak_dialog('fhem.error.setup')
            return
        allowed_types = ['light']
        device = message.data["Device"]

        try:
            brightness_req = float(message.data["BrightnessValue"])
            if brightness_req > 100 or brightness_req < 0:
                self.speak_dialog('fhem.brightness.badreq')
        except KeyError:
            brightness_req = 10.0
        brightness_value = int(brightness_req / 100 * 255)
        # brightness_percentage = int(brightness_req) # debating use
        LOG.debug("device: %s" % device)
        LOG.debug("Brightness Value: %s" % brightness_value)
        try:
            fhem_device = self.fhem.find_device(device, allowed_types)
        except ConnectionError:
            self.speak_dialog('fhem.error.offline')
            return
        if fhem_device is None:
            self.speak_dialog('fhem.device.unknown', data={
                              "dev_name": device})
            return
        fhem_data = {'device_id': fhem_device['id']}
        # IDEA: set context for 'turn it off again' or similar
        # self.set_context('Entity', fhem_entity['dev_name'])

        # if self.lang == 'de':
        #    if action == 'runter' or action == 'dunkler':
        #        action = 'dim'
        #    elif action == 'heller' or action == 'hell':
        #        action = 'brighten'
        if "DecreaseVerb" in message.data or \
                "LightDimVerb" in message.data:
            if fhem_device['state'] == "off":
                self.speak_dialog('fhem.brightness.cantdim.off',
                                  data=fhem_device)
            else:
                light_attrs = self.fhem.find_entity_attr(fhem_device['id'])
                if light_attrs['unit_measure'] is None:
                    self.speak_dialog(
                        'fhem.brightness.cantdim.dimmable',
                        data=fhem_device)
                else:
                    fhem_data['brightness'] = light_attrs['unit_measure']
                    if fhem_data['brightness'] < brightness_value:
                        fhem_data['brightness'] = 10
                    else:
                        fhem_data['brightness'] -= brightness_value
                    self.fhem.execute_service("fhem", "turn_on", fhem_data)
                    fhem_data['dev_name'] = fhem_device['dev_name']
                    self.speak_dialog('fhem.brightness.decreased',
                                      data=fhem_data)
        elif "IncreaseVerb" in message.data or \
                "LightBrightenVerb" in message.data:
            if fhem_device['state'] == "off":
                self.speak_dialog(
                    'fhem.brightness.cantdim.off',
                    data=fhem_device)
            else:
                light_attrs = self.fhem.find_entity_attr(fhem_device['id'])
                if light_attrs['unit_measure'] is None:
                    self.speak_dialog(
                        'fhem.brightness.cantdim.dimmable',
                        data=fhem_device)
                else:
                    fhem_data['brightness'] = light_attrs['unit_measure']
                    if fhem_data['brightness'] > brightness_value:
                        fhem_data['brightness'] = 255
                    else:
                        fhem_data['brightness'] += brightness_value
                    self.fhem.execute_service("fhem", "turn_on", fhem_data)
                    fhem_data['dev_name'] = fhem_device['dev_name']
                    self.speak_dialog('fhem.brightness.increased',
                                      data=fhem_data)
        else:
            self.speak_dialog('fhem.error.sorry')
            return

    @intent_handler(AdaptIntent().require("AutomationActionKeyword")
                    .require("Entity"))
    def handle_automation_intent(self, message):
        # TODO not supported yet
        self.speak_dialog('fhem.error.notsupported')
        return
        #
        self._setup()
        if self.fhem is None:
            self.speak_dialog('fhem.error.setup')
            return
        entity = message.data["Entity"]
        allowed_types = ['automation', 'scene', 'script']  # TODO
        LOG.debug("Entity: %s" % entity)
        # also handle scene and script requests
        try:
            fhem_entity = self.fhem.find_device(entity, allowed_types)
        except ConnectionError:
            self.speak_dialog('fhem.error.offline')
            return
        fhem_data = {'entity_id': fhem_entity['id']}
        if fhem_entity is None:
            self.speak_dialog('fhem.device.unknown', data={
                              "dev_name": entity})
            return

        # IDEA: set context for 'turn it off again' or similar
        # self.set_context('Entity', fhem_entity['dev_name'])

        LOG.debug("Triggered automation/scene/script: {}".format(fhem_data))
        if "automation" in fhem_entity['id']:
            self.fhem.execute_service('automation', 'trigger', fhem_data)
            self.speak_dialog('fhem.automation.trigger',
                              data={"dev_name": fhem_entity['dev_name']})
        elif "script" in fhem_entity['id']:
            self.speak_dialog('fhem.automation.trigger',
                              data={"dev_name": fhem_entity['dev_name']})
            self.fhem.execute_service("fhem", "turn_on", data=fhem_data)
        elif "scene" in fhem_entity['id']:
            self.speak_dialog('fhem.device.on',
                              data=fhem_entity)
            self.fhem.execute_service("fhem", "turn_on", data=fhem_data)

    @intent_file_handler('sensor.intent')
    def handle_sensor_intent(self, message):
        self._setup()
        if self.fhem is None:
            self.speak_dialog('fhem.error.setup')
            return

        device = message.data.get("device")
        if message.data.get("room"):
            room = message.data.get("room")
        else:
            # if no room is given use device location
            room = self.device_location
        allowed_types = '(sensor|thermometer)'
        LOG.debug("device: %s" % device)
        try:
            fhem_device = self._find_device(device, allowed_types, room)
        except ConnectionError:
            self.speak_dialog('fhem.error.offline')
            return
        if fhem_device is None:
            self.speak_dialog('fhem.device.unknown', data={
                              "dev_name": device})
            return

        device = fhem_device['id']
        sensor_name = fhem_device['dev_name']
        sensor_state = ""
        sensor_unit = ""

        sensor_values = self.translate_namedvalues('sensor.value')
        tokens = fhem_device['state']['Value'].split(" ")
        for t in range(0, len(tokens)):
            tok = tokens[t].lower().replace(":", "")
            # LOG.debug("tok = %s" % tok)
            if tok in ['t', 'temp', 'temperatur', 'temperature']:
                sensor_state += sensor_values["temperature"]
            elif tok in ['h', 'hum', 'humidity']:
                sensor_state += sensor_values["humidity"]
            elif tok in ['p', 'pamb', 'press', 'pressure']:
                sensor_state += sensor_values["pressure"]
            else:
                sensor_state += tokens[t]
            sensor_state += " "

        LOG.debug("fhem_device['state']['Value']: %s" %
                  fhem_device['state']['Value'])
        LOG.debug("sensor_state: %s" % sensor_state)
        self.speak_dialog('fhem.sensor', data={
             "dev_name": sensor_name,
             "value": sensor_state,
             "unit": sensor_unit})

        # # IDEA: set context for 'read it out again' or similar
        # # self.set_context('Entity', fhem_entity['dev_name'])
        #
        # unit_measurement = self.fhem.find_entity_attr(entity)
        # if unit_measurement[0] is not None:
        #     sensor_unit = unit_measurement[0]
        # else:
        #     sensor_unit = ''
        #
        # sensor_name = unit_measurement[1]
        # sensor_state = unit_measurement[2]
        # # extract unit for correct pronounciation
        # # this is fully optional
        # try:
        #     from quantulum import parser
        #     quantulumImport = True
        # except ImportError:
        #     quantulumImport = False
        #
        # if quantulumImport and unit_measurement != '':
        #     quantity = parser.parse((u'{} is {} {}'.format(
        #         sensor_name, sensor_state, sensor_unit)))
        #     if len(quantity) > 0:
        #         quantity = quantity[0]
        #         if (quantity.unit.name != "dimensionless" and
        #                 quantity.uncertainty <= 0.5):
        #             sensor_unit = quantity.unit.name
        #             sensor_state = quantity.value
        #
        # self.speak_dialog('fhem.sensor', data={
        #     "dev_name": sensor_name,
        #     "value": sensor_state,
        #     "unit": sensor_unit})
        # # IDEA: Add some context if the person wants to look the unit up
        # # Maybe also change to name
        # # if one wants to look up "outside temperature"
        # # self.set_context("SubjectOfInterest", sensor_unit)

    @intent_file_handler('presence.intent')
    def handle_presence_intent(self, message):
        self._setup()
        if self.fhem is None:
            self.speak_dialog('fhem.error.setup')
            return
        wanted = message.data["entity"]
        LOG.debug("wanted: %s" % wanted)

        try:
            roommates = self.fhem.get(room=self.allowed_devices_room,
                                      device_type='ROOMMATE')
        except ConnectionError:
            self.speak_dialog('fhem.error.offline')
            return

        if len(roommates) < 1:
            self.speak_dialog('fhem.presence.error')
            return

        presence = None
        bestRatio = 66

        for rm in roommates:
            if 'rr_realname' in rm['Attributes'].keys():
                realname = rm['Attributes'][rm['Attributes']['rr_realname']]
                LOG.debug("realname: %s" % realname)
                ratio = fuzz.ratio(wanted.lower(), realname.lower(),
                                   score_cutoff=bestRatio)
                LOG.debug("ratio: %s" % ratio)
                if ratio > bestRatio:
                    presence = rm['Readings']['presence']['Value']
                    bestName = realname
                    bestRatio = ratio

        presence_values = self.translate_namedvalues('presence.value')
        if presence:
            location = presence_values[presence]
            self.speak_dialog('fhem.presence.found',
                              data={'wanted': bestName,
                                    'location': location})
        else:
            self.speak_dialog('fhem.presence.error')

    @intent_file_handler('set.climate.intent')
    def handle_set_thermostat_intent(self, message):
        self._setup()
        if self.fhem is None:
            self.speak_dialog('fhem.error.setup')
            return
        LOG.debug("Starting Thermostat Intent")

        if message.data.get("device"):
            device = message.data.get("device")
        else:
            device = "thermostat"
        if message.data.get("room"):
            room = message.data.get("room")
        else:
            room = self.device_location

        LOG.debug("Device: %s" % device)
        LOG.debug("This is the message data: %s" % message.data)
        temperature = message.data["temp"]
        LOG.debug("desired temperature from message: %s" % temperature)

        allowed_types = 'thermostat'
        try:
            fhem_device = self._find_device(device, allowed_types, room)
        except ConnectionError:
            self.speak_dialog('fhem.error.offline')
            return
        if fhem_device is None:
            self.speak_dialog('fhem.device.unknown', data={"dev_name": device})
            return
        LOG.debug("Entity State: %s" % fhem_device['state'])

        device_id = fhem_device['id']
        target_device = device_id

        # defaults for min/max temp and step
        minValue = 5.0
        maxValue = 35.0
        minStep = 0.5
        unit = ""
        cmd = ""

        # check thermostat type, derive command and min/max values
        LOG.debug("fhem_device: %s" % fhem_device)
        # for that get thermostat device
        td = self.fhem.get_device(fhem_device['id'])
        if len(td) != 1:
            self.speak_dialog('fhem.device.unknown', data={"dev_name": device})
            return
        td = td[0]
        LOG.debug("td: %s" % td)
        if 'desired-temp' in td['Readings']:
            cmd = "desired-temp"
            if ('FBTYPE' in td['Readings']) and \
               (td['Readings']['FBTYPE'] == 'Comet DECT'):
                # LOG.debug("Comet DECT")
                minValue = 8.0
                maxValue = 28.0
            elif td['Internals']['TYPE'] == 'FHT':
                # LOG.debug("FHT")
                minValue = 6.0
                maxValue = 30.0
            elif td['Internals']['TYPE'] == 'CUL_HM':
                LOG.debug("HM")
                # test for Clima-Subdevice
                if 'channel_04' in td['Internals']:
                    target_device = td['Internals']['channel_04']
        elif 'desiredTemperature' in td['Readings']:
            # LOG.debug("MAX")
            cmd = "desiredTemperature"
            minValue = 4.5
            maxValue = 30.5
        elif 'desired' in td['Readings']:
            # LOG.debug("PID20")
            cmd = "desired"
        elif 'homebridgeMapping' in td['Attributes']:
            LOG.debug("homebridgeMapping")
            hbm = td['Attributes']['homebridgeMapping'].split(" ")
            for h in hbm:
                # TargetTemperature=desired-temp::desired-temp,
                # minValue=5,maxValue=35,minStep=0.5,nocache=1
                if h.startswith("TargetTemperature"):
                    targettemp = (h.split("=", 1)[1]).split(",")
                    LOG.debug("targettemp = %s" % targettemp)
                    for t in targettemp:
                        LOG.debug("t = %s" % t)
                        if t.startswith("desired-temp"):
                            t2 = t.split(":")
                            cmd = t2[0]
                            if t2[1] != '':
                                target_device = t2[1]
                        elif t.startswith("minValue"):
                            minValue = float(t.split("=")[1])
                        elif t.startswith("maxValue"):
                            maxValue = float(t.split("=")[1])
                        elif t.startswith("minStep"):
                            minStep = float(t.split("=")[1])

        if not cmd:
            LOG.info("FHEM device %s has unknown thermostat type" % device_id)
            self.speak_dialog('fhem.error.notsupported')
            return

        LOG.debug("target_device: %s cmd: %s" % (target_device, cmd))
        LOG.debug("minValue: %s maxValue: %s minStep: %s" % (minValue, maxValue,
                                                             minStep))

        # check if desired temperature is out of bounds
        if (float(temperature) < minValue) or (float(temperature) > maxValue) \
           or (float(temperature) % minStep != 0.0):
            self.speak_dialog('fhem.thermostat.badreq',
                              data={"minValue": minValue,
                                    "maxValue": maxValue,
                                    "minStep": minStep})
            return

        action = "%s %s" % (cmd, temperature)
        LOG.debug("set %s %s" % (target_device, action))
        self.fhem.send_cmd("set {} {}".format(target_device, action))
        self.speak_dialog('fhem.set.thermostat',
                          data={
                              "dev_name": device,
                              "value": temperature,
                              "unit": unit})

    def handle_fallback(self, message):
        LOG.debug("entering handle_fallback with utterance '%s'" %
                  message.data.get('utterance'))
        self._setup()
        if self.fhem is None:
            LOG.debug("FHEM setup error")
            self.speak_dialog('fhem.error.setup')
            return False
        if not self.enable_fallback:
            LOG.debug("fallback not enabled!")
            return False

        # pass message to FHEM-server
        try:
            # TODO check response after switch to python-fhem lib
            if self.fallback_device_type == "TEERKO":
                # LOG.debug("fallback device type TEERKO")
                response = self.fhem.send_cmd(
                    "set {} TextCommand {}".format(self.fallback_device_name,
                                                   message.data.get('utterance')))
            elif self.fallback_device_type == "Talk2Fhem":
                # LOG.debug("fallback device type Talk2Fhem")
                response = self.fhem.send_cmd(
                    "set {} {}".format(self.fallback_device_name,
                                       message.data.get('utterance')))
            elif self.fallback_device_type == "Babble":
                # LOG.debug("fallback device type Babble")
                cmd = '{Babble_DoIt("%s","%s","testit","1")}' % \
                    (self.fallback_device_name, message.data.get('utterance'))
                response = self.fhem.send_cmd(cmd)
                # Babble gives feedback through response
                # existence of string '[Babble_Normalize]' means success!
                if response.text.find('[Babble_Normalize]') > 0:
                    return True
                else:
                    return False
            else:
                LOG.debug("fallback device type UNKNOWN")
                return False
        except ConnectionError:
            LOG.debug("connection error")
            self.speak_dialog('fhem.error.offline')
            return False

        fdn = self.fallback_device_name
        result = self.fhem.get_readings(name=fdn)
        LOG.debug("result: %s" % result)

        if not result:
            # LOG.debug("no result")
            return False

        answer = ""
        if self.fallback_device_type == "Talk2Fhem":
            if result[fdn]['status']['Value'] == 'answers':
                # LOG.debug("answering with Talk2Fhem result")
                answer = result[fdn]['answers']['Value']
            else:
                return False
        elif self.fallback_device_type == "TEERKO":
            if result[fdn]['Answer']['Value'] is not None:
                # LOG.debug("answering with TEERKO result")
                answer = result[fdn]['Answer']['Value']
            else:
                return False
        # Babble gives feedback through response, so nothing to do here
        else:
            # LOG.debug("status undefined")
            return False

        if answer == "":
            # LOG.debug("empty answer")
            return False

        asked_question = False
        # TODO: maybe enable conversation here if server asks sth like
        # "In which room?" => answer should be directly passed to this skill
        if answer.endswith("?"):
            LOG.debug("answer endswith question mark")
            asked_question = True
        self.speak(answer, expect_response=asked_question)
        return True

    def _find_device(self, device, allowed_types, room=""):
        LOG.debug("device: {} allowed_types: {} room: {}".format(device,
                                                                 allowed_types,
                                                                 room))
        filter_dict = {'genericDeviceType': allowed_types}

        # new search strategy: first check if there is a fit in specified room
        if room:
            room = self._normalize(self._clean_common_words(room))
            # LOG.debug("normalized room: {}".format(room))
            filter_dict['room'] = room
        device_candidates = self.fhem.get(room=self.allowed_devices_room,
                                          filters=filter_dict)

        if len(device_candidates) == 1:
            # TODO can we do anything if len(...) > 1 ?
            LOG.debug("perfect match")
            # we have a perfect match:
            # there is only one device of the allowed type in the room
            dc = device_candidates[0]
            best_device = {"id": dc['Name'],
                           "dev_name": self._get_aliasname(dc),
                           "state": dc['Readings']['state'],
                           "best_score": 999}
            return best_device

        # try again without filter on room
        if 'room' in filter_dict.keys():
            LOG.debug("try again without filter on room")
            del filter_dict['room']
        device_candidates = self.fhem.get(room=self.allowed_devices_room,
                                          filters=filter_dict)
        # LOG.debug(device_candidates)

        # require a score above 50%
        best_score = 50
        best_device = None

        if device_candidates:
            for dc in device_candidates:
                # LOG.debug("==================================================")
                norm_name = self._normalize(dc['Name'])
                norm_name_list = norm_name.split(" ")
                # LOG.debug("norm_name_list = %s" % norm_name_list)

                dev_room = self._get_normalized_room_list(dc)
                for r in dev_room:
                    if (r not in norm_name_list):
                        norm_name += (" " + self._normalize(r))

                # LOG.debug("dev_room: {}".format(dev_room))
                # LOG.debug("norm_name = %s" % norm_name)

                alias = self._get_aliasname(dc)
                norm_alias = self._normalize(alias)

                try:
                    if (norm_name != norm_alias) and ('alias' in
                                                      dc['Attributes']):
                        score = fuzz.token_sort_ratio(
                            device,
                            norm_alias)
                        # add bonus if room name match
                        if room and dev_room:
                            score += self._get_bonus_for_room(room,
                                                              dev_room[0])
                        if score > best_score:
                            best_score = score
                            best_device = {
                                "id": dc['Name'],
                                "dev_name": alias,
                                "state": dc['Readings']['state'],
                                "best_score": best_score}

                    score = fuzz.token_sort_ratio(device, norm_name)
                    # add bonus if room name match
                    if room and dev_room:
                        score += self._get_bonus_for_room(room, dev_room[0])
                    # LOG.debug("%s %s" % (norm_name, score))
                    if score > best_score:
                        best_score = score
                        best_device = {
                            "id": dc['Name'],
                            "dev_name": alias,
                            "state": dc['Readings']['state'],
                            "best_score": best_score}

                except KeyError:
                    pass  # print("KeyError")
            LOG.debug("best device = %s" % best_device)
            return best_device

    def _get_bonus_for_room(self, room, dev_room):
        if fuzz.ratio(room, dev_room) > REQUIRED_RATIO_FOR_BONUS:
            LOG.debug("bonus! {} {}".format(room, dev_room))
            return BONUS
        else:
            return 0

    def _get_aliasname(self, device):
        if 'alias' in device['Attributes']:
            alias = device['Attributes']['alias']
        else:
            alias = device['Name']
        return alias

    def _get_normalized_room_list(self, dev):
        # add device room to name
        dev_room = []
        # LOG.debug(self.ignore_rooms)
        ignore = [x.lower() for x in self.ignore_rooms.split(",")]
        # LOG.debug("ignore = %s" % ignore)
        if 'room' in dev['Attributes']:
            rooms = [x.lower() for x in dev['Attributes']['room'].split(",")]
            rooms.remove(self.allowed_devices_room.lower())
            # LOG.debug("rooms = %s" % rooms)
            for r in rooms:
                # LOG.debug("r = %s" % r)
                if (r not in ignore):
                    # LOG.debug("adding r = %s" % r)
                    dev_room.append(r)
        return dev_room

    def _normalize(self, name):
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
        return s2.replace("_", " ").replace("-", " ").replace(".", " ")

    def _clean_common_words(self, text):
        txt = text.split(" ")
        common_words = self.translate_list("common.words")
        # LOG.debug("common_words {}".format(common_words))
        for i in range(0, len(txt)):
            if txt[i] in common_words:
                txt[i] = ""
        res = ""
        for t in txt:
            res += "{} ".format(t)
        prev_len = len(res) + 1
        while prev_len > len(res):
            res.replace("  ", " ")
            prev_len = len(res)
        # LOG.debug("out {}".format(res))
        return res.strip()

    def shutdown(self):
        self.remove_fallback(self.handle_fallback)
        super(FhemSkill, self).shutdown()

    def stop(self):
        pass

    def __translate(self, term, data=None):
        try:
            return self.dialog_renderer.render(term, data)
        except BaseException:
            # no dialog at all (e.g. unsupported language or unknown term
            return term


def create_skill():
    return FhemSkill()
