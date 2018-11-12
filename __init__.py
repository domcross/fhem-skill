from adapt.intent import IntentBuilder
from mycroft import MycroftSkill, intent_handler, AdaptIntent, intent_file_handler
from mycroft.skills.core import FallbackSkill
from mycroft.util.log import LOG

from os.path import dirname, join
from requests.exceptions import ConnectionError

from .fhem_client import FhemClient

__author__ = 'domcross, robconnolly, btotharye, nielstron'

# Timeout time for requests
TIMEOUT = 10

class FhemSkill(FallbackSkill):

    def __init__(self):
        super(FhemSkill, self).__init__(name="FhemSkill")
        LOG.info("__init__")
        self.fhem = None
        self.enable_fallback = False

    def _setup(self, force=False):
        if self.settings is not None and (force or self.fhem is None):
            LOG.debug("_setup")
            portnumber = self.settings.get('portnum')
            try:
                portnumber = int(portnumber)
            except TypeError:
                portnumber = 8083
            except ValueError:
                # String might be some rubbish (like '')
                portnumber = 0

            self.fhem = FhemClient(
                self.settings.get('host'),
                self.settings.get('username'),
                self.settings.get('password'),
                portnumber,
                self.settings.get('room'),
                self.settings.get('ignore_rooms'),
                self.settings.get('ssl') == True,
                self.settings.get('verify') == True
            )
            if self.fhem:
                # Check if natural language control is loaded at fhem-server
                # and activate fallback accordingly
                LOG.debug("fallback_device_name %s" %
                          self.settings.get('fallback_device_name'))
                LOG.debug("enable_fallback %s" %
                          self.settings.get('enable_fallback'))
                if self.settings.get('enable_fallback') == True and \
                    self.settings.get('fallback_device_name') is not None:
                    fallback_device = self.fhem.get_device("NAME",
                                    self.settings.get('fallback_device_name'))
                    if fallback_device:
                        self.fallback_device_name = fallback_device['Name']
                        self.fallback_device_type = \
                                fallback_device['Internals']['TYPE']
                        LOG.debug("fallback_device_type is %s" % self.fallback_device_type)
                        if self.fallback_device_type in ["Talk2Fhem","TEERKO",
                                                        "Babble"]:
                            self.enable_fallback = True
                        else:
                            self.enable_fallback = False
                else:
                    self.enable_fallback = False
                LOG.debug('fhem-fallback enabled: %s' % self.enable_fallback)


    def _force_setup(self):
        LOG.debug('Creating a new Fhem-Client')
        self._setup(True)

    def initialize(self):
        # Needs higher priority than general fallback skills
        self.register_fallback(self.handle_fallback, 2)
        # Check and then monitor for credential changes
        self.settings.set_changed_callback(self.on_websettings_changed)

    def on_websettings_changed(self):
        # Only attempt to load if the host is set
        LOG.debug("websettings changed")
        if self.settings.get('host', None):
            try:
                self._setup(True)
            except Exception:
                pass

    @intent_handler(AdaptIntent().require("SwitchActionKeyword")
                    .require("Action").require("Entity"))
    def handle_switch_intent(self, message):
        self._setup()
        if self.fhem is None:
            self.speak_dialog('fhem.error.setup')
            return
        LOG.debug("Starting Switch Intent")
        entity = message.data["Entity"]
        action = message.data["Action"]
        allowed_types = ['light', 'switch', 'outlet']
        LOG.debug("Entity: %s" % entity)
        LOG.debug("Action: %s" % action)
        # TODO if entity is 'all', 'any' or 'every' turn on
        # every single entity not the whole group
        try:
            fhem_entity = self.fhem.find_device(entity, allowed_types)
        except ConnectionError:
            self.speak_dialog('fhem.error.offline')
            return
        if fhem_entity is None:
            self.speak_dialog('fhem.device.unknown', data={"dev_name": entity})
            return
        LOG.debug("Entity State: %s" % fhem_entity['state'])
        # fhem_data = {'entity_id': fhem_entity['id']}

        # IDEA: set context for 'turn it off' again or similar
        # self.set_context('Entity', fhem_entity['dev_name'])

        # keep original actioname for speak_dialog
        # when device already is in desiredstate
        original_action = action
        if self.lang.lower().startswith("de"):
            if (action == 'ein') or (action == 'an'):
                action = 'on'
            elif action == 'aus':
                action = 'off'
        LOG.debug("- action: %s" % action)
        LOG.debug("- state: %s" % fhem_entity['state']['Value'])
        if fhem_entity['state']['Value'] == action:
            LOG.debug("Entity in requested state")
            self.speak_dialog('fhem.device.already', data={
                'dev_name': fhem_entity['dev_name'],
                'action': original_action})
        elif action == "toggle":
            if(fhem_entity['state']['Value'] == 'off'):
                action = 'on'
            else:
                action = 'off'
            LOG.debug("toggled action: %s" % action)
            self.fhem.execute_service("set", fhem_entity['id'], action)
            self.speak_dialog('fhem.device.%s' % action, data=fhem_entity)
        elif action in ["on", "off"]:
            LOG.debug("action: on/off")
            self.speak_dialog('fhem.device.%s' % action, data=fhem_entity)
            self.fhem.execute_service("set", fhem_entity['id'], action)
        else:
            self.speak_dialog('fhem.error.sorry')
            return

    @intent_handler(AdaptIntent().optionally("LightsKeyword")
                    .require("SetVerb").require("Entity")
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
        entity = message.data["Entity"]
        allowed_types = ['light']  # TODO
        try:
            brightness_req = float(message.data["BrightnessValue"])
            if brightness_req > 100 or brightness_req < 0:
                self.speak_dialog('fhem.brightness.badreq')
        except KeyError:
            brightness_req = 10.0
        brightness_value = int(brightness_req / 100 * 255)
        brightness_percentage = int(brightness_req)
        LOG.debug("Entity: %s" % entity)
        LOG.debug("Brightness Value: %s" % brightness_value)
        LOG.debug("Brightness Percent: %s" % brightness_percentage)
        try:
            fhem_entity = self.fhem.find_device(entity, allowed_types)
        except ConnectionError:
            self.speak_dialog('fhem.error.offline')
            return
        if fhem_entity is None:
            self.speak_dialog('fhem.device.unknown', data={
                              "dev_name": entity})
            return
        fhem_data = {'entity_id': fhem_entity['id']}

        # IDEA: set context for 'turn it off again' or similar
        # self.set_context('Entity', fhem_entity['dev_name'])

        # TODO - Allow value set
        if "SetVerb" in message.data:
            fhem_data['brightness'] = brightness_value
            fhem_data['dev_name'] = fhem_entity['dev_name']
            self.fhem.execute_service("fhem", "turn_on", fhem_data)
            self.speak_dialog('fhem.brightness.dimmed',
                              data=fhem_data)
        else:
            self.speak_dialog('fhem.error.sorry')
            return

    @intent_handler(AdaptIntent().optionally("LightsKeyword")
                    .one_of("IncreaseVerb", "DecreaseVerb",
                            "LightBrightenVerb", "LightDimVerb")
                    .require("Entity").optionally("BrightnessValue"))
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
        entity = message.data["Entity"]

        try:
            brightness_req = float(message.data["BrightnessValue"])
            if brightness_req > 100 or brightness_req < 0:
                self.speak_dialog('fhem.brightness.badreq')
        except KeyError:
            brightness_req = 10.0
        brightness_value = int(brightness_req / 100 * 255)
        # brightness_percentage = int(brightness_req) # debating use
        LOG.debug("Entity: %s" % entity)
        LOG.debug("Brightness Value: %s" % brightness_value)
        try:
            fhem_entity = self.fhem.find_device(entity, allowed_types)
        except ConnectionError:
            self.speak_dialog('fhem.error.offline')
            return
        if fhem_entity is None:
            self.speak_dialog('fhem.device.unknown', data={
                              "dev_name": entity})
            return
        fhem_data = {'entity_id': fhem_entity['id']}
        # IDEA: set context for 'turn it off again' or similar
        # self.set_context('Entity', fhem_entity['dev_name'])

        # if self.lang == 'de':
        #    if action == 'runter' or action == 'dunkler':
        #        action = 'dim'
        #    elif action == 'heller' or action == 'hell':
        #        action = 'brighten'
        if "DecreaseVerb" in message.data or \
                "LightDimVerb" in message.data:
            if fhem_entity['state'] == "off":
                self.speak_dialog('fhem.brightness.cantdim.off',
                                  data=fhem_entity)
            else:
                light_attrs = self.fhem.find_entity_attr(fhem_entity['id'])
                if light_attrs['unit_measure'] is None:
                    self.speak_dialog(
                        'fhem.brightness.cantdim.dimmable',
                        data=fhem_entity)
                else:
                    fhem_data['brightness'] = light_attrs['unit_measure']
                    if fhem_data['brightness'] < brightness_value:
                        fhem_data['brightness'] = 10
                    else:
                        fhem_data['brightness'] -= brightness_value
                    self.fhem.execute_service("fhem", "turn_on", fhem_data)
                    fhem_data['dev_name'] = fhem_entity['dev_name']
                    self.speak_dialog('fhem.brightness.decreased',
                                      data=fhem_data)
        elif "IncreaseVerb" in message.data or \
                "LightBrightenVerb" in message.data:
            if fhem_entity['state'] == "off":
                self.speak_dialog(
                    'fhem.brightness.cantdim.off',
                    data=fhem_entity)
            else:
                light_attrs = self.fhem.find_entity_attr(fhem_entity['id'])
                if light_attrs['unit_measure'] is None:
                    self.speak_dialog(
                        'fhem.brightness.cantdim.dimmable',
                        data=fhem_entity)
                else:
                    fhem_data['brightness'] = light_attrs['unit_measure']
                    if fhem_data['brightness'] > brightness_value:
                        fhem_data['brightness'] = 255
                    else:
                        fhem_data['brightness'] += brightness_value
                    self.fhem.execute_service("fhem", "turn_on", fhem_data)
                    fhem_data['dev_name'] = fhem_entity['dev_name']
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
        allowed_types = ['automation', 'scene', 'script'] # TODO
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

    @intent_handler(AdaptIntent().require("SensorStatusKeyword")
                    .require("Entity"))
    def handle_sensor_intent(self, message):
        self._setup()
        if self.fhem is None:
            self.speak_dialog('fhem.error.setup')
            return

        entity = message.data["Entity"]
        allowed_types = ['sensor', 'thermometer']  # TODO
        LOG.debug("Entity: %s" % entity)
        try:
            fhem_entity = self.fhem.find_device(entity, allowed_types)
        except ConnectionError:
            self.speak_dialog('fhem.error.offline')
            return
        if fhem_entity is None:
            self.speak_dialog('fhem.device.unknown', data={
                              "dev_name": entity})
            return

        entity = fhem_entity['id']
        sensor_name = fhem_entity['dev_name']
        sensor_state = ""
        sensor_unit = ""

        tokens = fhem_entity['state']['Value'].split(" ")
        for t in range(0, len(tokens)):
            tok = tokens[t].lower().replace(":", "")
            # LOG.debug("tok = %s" % tok)
            if tok in ['t', 'temp', 'temperatur', 'temperature']:
                sensor_state += self.__translate("sensor.temperature")
            elif tok in ['h', 'hum', 'humidity']:
                sensor_state += self.__translate("sensor.humidity")
            elif tok in ['p', 'pamb', 'press', 'pressure']:
                sensor_state += self.__translate("sensor.pressure")
            else:
                sensor_state += tokens[t]
            sensor_state += " "

        LOG.debug("fhem_entity['state']['Value']: %s" %
                  fhem_entity['state']['Value'])
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

    # In progress, still testing.
    # Device location works.
    # Proximity might be an issue
    # - overlapping command for directions modules
    # - (e.g. "How far is x from y?")
    @intent_handler(AdaptIntent().require("DeviceTrackerKeyword")
                    .require("Entity"))
    def handle_tracker_intent(self, message):
        # TODO not supported yet
        self.speak_dialog('fhem.error.notsupported')
        return
        #
        self._setup()
        if self.fhem is None:
            self.speak_dialog('fhem.error.setup')
            return
        entity = message.data["Entity"]
        allowed_types = ['device_tracker']  # TODO
        LOG.debug("Entity: %s" % entity)
        try:
            fhem_entity = self.fhem.find_device(entity, allowed_types)
        except ConnectionError:
            self.speak_dialog('fhem.error.offline')
            return
        if fhem_entity is None:
            self.speak_dialog('fhem.device.unknown', data={"dev_name": entity})
            return

        # IDEA: set context for 'locate it again' or similar
        # self.set_context('Entity', fhem_entity['dev_name'])

        entity = fhem_entity['id']
        dev_name = fhem_entity['dev_name']
        dev_location = fhem_entity['state']
        self.speak_dialog('fhem.tracker.found',
                          data={'dev_name': dev_name,
                                'location': dev_location})

    @intent_file_handler('set.climate.intent')
    def handle_set_thermostat_intent(self, message):
        self._setup()
        if self.fhem is None:
            self.speak_dialog('fhem.error.setup')
            return
        LOG.debug("Starting Thermostat Intent")

        entity = message.data["entity"]
        LOG.debug("Entity: %s" % entity)
        LOG.debug("This is the message data: %s" % message.data)
        temperature = message.data["temp"]
        LOG.debug("desired temperature from message: %s" % temperature)

        allowed_types = ['thermostat']
        try:
            fhem_entity = self.fhem.find_device(entity, allowed_types)
        except ConnectionError:
            self.speak_dialog('fhem.error.offline')
            return
        if fhem_entity is None:
            self.speak_dialog('fhem.device.unknown', data={"dev_name": entity})
            return
        LOG.debug("Entity State: %s" % fhem_entity['state'])

        entity_id = fhem_entity['id']
        target_entity = entity_id

        # defaults for min/max temp and step
        minValue = 5.0
        maxValue = 35.0
        minStep = 0.5
        unit = ""
        cmd = ""

        # check thermostat type, derive command and min/max values
        LOG.debug("fhem_entity: %s" % fhem_entity)
        # for that get thermostat device
        td = self.fhem.get_device("NAME",fhem_entity['id'])
        LOG.debug("td: %s" % td)
        if 'desired-temp' in td['Readings']:
            cmd = "desired-temp"
            if 'FBTYPE' in td['Readings'] and \
                td['Readings']['FBTYPE']=='Comet DECT':
                #LOG.debug("Comet DECT")
                minValue=8.0
                maxValue=28.0
            elif td['Internals']['TYPE']=='FHT':
                #LOG.debug("FHT")
                minValue=6.0
                maxValue=30.0
            elif td['Internals']['TYPE']=='CUL_HM':
                #LOG.debug("HM")
                # test for Clima-Subdevice
                if 'channel_04' in td['Internals']:
                    target_entity = td['Internals']['channel_04']
        elif 'desiredTemperature' in td['Readings']:
            #LOG.debug("MAX")
            cmd = "desiredTemperature"
            minValue=4.5
            maxValue=30.5
        elif 'desired' in td['Readings']:
            #LOG.debug("PID20")
            cmd = "desired"
        elif 'homebridgeMapping' in td['Attributes']:
            LOG.debug("homebridgeMapping")
            hbm = td['Attributes']['homebridgeMapping'].split(" ")
            for h in hbm:
                #TargetTemperature=desired-temp::desired-temp,
                #minValue=5,maxValue=35,minStep=0.5,nocache=1
                if h.startswith("TargetTemperature"):
                    targettemp = (h.split("=",1)[1]).split(",")
                    LOG.debug("targettemp = %s" % targettemp)
                    for t in targettemp:
                        LOG.debug("t = %s" % t)
                        if t.startswith("desired-temp"):
                            t2 = t.split(":")
                            cmd = t2[0]
                            if t2[1] != '':
                                target_entity = t2[1]
                        elif t.startswith("minValue"):
                            minValue = float(t.split("=")[1])
                        elif t.startswith("maxValue"):
                            maxValue = float(t.split("=")[1])
                        elif t.startswith("minStep"):
                            minStep = float(t.split("=")[1])

        if cmd=="":
            LOG.info("FHEM device %s has unknown thermostat type" % entity_id)
            self.speak_dialog('fhem.error.notsupported')
            return

        LOG.debug("target_entity: %s cmd: %s" % (target_entity, cmd))
        LOG.debug("minValue: %s maxValue: %s minStep: %s" % (minValue,maxValue,
                    minStep))

        # check if desired temperature is out of bounds
        if (float(temperature)<minValue) or (float(temperature)>maxValue) or \
                (float(temperature) % minStep != 0.0):
            self.speak_dialog('fhem.thermostat.badreq',
                          data={"minValue": minValue,
                                "maxValue": maxValue,
                                "minStep": minStep})
            return

        action = "%s %s" % (cmd, temperature)
        LOG.debug("set %s %s" % (target_entity, action))
        self.fhem.execute_service("set", target_entity, action)
        self.speak_dialog('fhem.set.thermostat',
                          data={
                              "dev_name": entity,
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
            if self.fallback_device_type == "TEERKO":
                #LOG.debug("fallback device type TEERKO")
                response = self.fhem.execute_service("set",
                        self.fallback_device_name,
                        "TextCommand {}".format(message.data.get('utterance')))
            elif self.fallback_device_type == "Talk2Fhem":
                #LOG.debug("fallback device type Talk2Fhem")
                response = self.fhem.execute_service("set",
                                                self.fallback_device_name,
                                                message.data.get('utterance'))
            elif self.fallback_device_type == "Babble":
                #LOG.debug("fallback device type Babble")
                cmd = '{Babble_DoIt("%s","%s","testit","1")}' % (self.fallback_device_name,
                                                message.data.get('utterance'))
                response = self.fhem.execute_service(cmd)
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

        result = self.fhem.get_device("NAME", self.fallback_device_name)
        #LOG.debug("result: %s" % result)

        if not result:  # or result['Readings']['status']['Value'] == 'err':
            #LOG.debug("no result")
            return False

        answer = ""
        if self.fallback_device_type == "Talk2Fhem":
            if result['Readings']['status']['Value'] == 'answers':
                #LOG.debug("answering with Talk2Fhem result")
                answer = result['Readings']['answers']['Value']
            else:
                return False
        elif self.fallback_device_type == "TEERKO":
            if result['Readings']['Answer']['Value'] is not None:
                #LOG.debug("answering with TEERKO result")
                answer = result['Readings']['Answer']['Value']
            else:
                return False
        # Babble gives feedback through response, so nothing to do here
        else:
            #LOG.debug("status undefined")
            return False

        if answer == "":
            #LOG.debug("empty answer")
            return False

        asked_question = False
        # TODO: maybe enable conversation here if server asks sth like
        # "In which room?" => answer should be directly passed to this skill
        if answer.endswith("?"):
            LOG.debug("answer endswith question mark")
            asked_question = True
        self.speak(answer, expect_response=asked_question)
        return True

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
