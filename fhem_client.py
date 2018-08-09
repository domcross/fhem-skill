from mycroft.util.log import LOG
from requests import get, post
from fuzzywuzzy import fuzz
import json
import re
import time

__author__ = 'domcross, btotharye'

# Timeout time for requests
TIMEOUT = 10


class FhemClient(object):
    def __init__(self, host, password, portnum, ssl=False, verify=True):
        LOG.debug("FhemClient __init__")
        self.ssl = ssl
        self.verify = verify
        if host is None or host == "":
            LOG.debug("set Host to internal default 192.168.100.96")
            host = "192.168.100.96"
        self.host = host
        if portnum is None or portnum == 0:
            LOG.debug("set Port to internal default 8083")
            portnum = 8083
        self.portnum = portnum
        if self.ssl:
            self.url = "https://%s:%d/fhem" % (host, portnum)
        else:
            self.url = "http://%s:%d/fhem" % (host, portnum)
        self.csrf_ts = 0 # on init force update of csrf-token
        self.csrf = "" #self._get_csrf()

        LOG.debug("csrf = %s" % self.csrf)
        self.headers = {
        #    'x-ha-access': password,
            'Content-Type': 'application/json'
        }
        self.room = "Homebridge" #TODO settings
        self.ignore_rooms = "IT,CUL_HM,ESPEasy,_LOG" #TODO settings


    def __get_csrf(self):
        # retrieve new csrf-token when older than 60 seconds
        if (time.time() - self.csrf_ts) > 60:
            self.csrf = get(self.url + "?XHR=1").headers['X-FHEM-csrfToken']
            self.csrf_ts = time.time()
        return self.csrf

    def _get_state(self):
        # devices auslesen
        command = "cmd=jsonlist2%20room={}&XHR=1".format(self.room)
        if self.ssl:
            req = get("%s?%s&fwcsrf=%s" %
                      (self.url, command, self.__get_csrf()),
                      headers=self.headers,
                      verify=self.verify,
                      timeout=TIMEOUT)
        else:
            req = get("%s?%s&fwcsrf=%s" %
                      (self.url, command, self.__get_csrf()),
                      headers=self.headers,
                      timeout=TIMEOUT)

        if req.status_code == 200:
            return req.json()
        else:
            pass

    def _normalize(self, name):
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
        return s2.replace("_"," ").replace("-"," ").replace(".", " ")

    def find_entity(self, entity, types):
        json_data = self._get_state()

        # require a score above 50%
        best_score = 50
        best_entity = None

        #types = ['security','ignore','switch','outlet','light','blind','thermometer',
        #         'thermostat','contact','garage','window','lock']

        if json_data:
            for state in json_data["Results"]:
                norm_name = self._normalize(state['Name'])
                norm_name_list = norm_name.split(" ")

                # add room to name
                room = ""
                ignore = self.ignore_rooms.split(",")
                if 'room' in state['Attributes']:
                    for r in state['Attributes']['room'].split(","):
                        if (r not in ignore) and (r not in norm_name_list):
                            room += (" " + r)

                norm_name += self._normalize(room)
                LOG.debug("norm_name = %s" % norm_name)

                if 'alias' in state['Attributes']:
                    alias = state['Attributes']['alias']
                else:
                    alias = state['Name']
                norm_alias = self._normalize(alias)

                try:
                    if any(n in norm_name_list for n in types) \
                        or (('genericDeviceType' in state['Attributes']) \
                            and (state['Attributes']['genericDeviceType'] in types))):
                        # something like temperature outside
                        # should score on "outside temperature sensor"
                        # and repetitions should not count on my behalf
                        if (norm_name!=norm_alias) and \
                           ('alias' in state['Attributes']):
                            score = fuzz.token_sort_ratio(
                                entity,
                                norm_alias)
                            if score > best_score:
                                best_score = score
                                best_entity = {
                                    "id": state['Name'],
                                    "dev_name": state['Attributes']['alias'],
                                    "state": state['Readings']['state'],
                                    "best_score": best_score}

                        score = fuzz.token_sort_ratio(
                            entity,
                            self._normalize(state['Name']))

                        if score > best_score:
                            best_score = score
                            best_entity = {
                                "id": state['Name'],
                                "dev_name": alias,
                                "state": state['Readings']['state'],
                                "best_score": best_score}
                except KeyError:
                    pass #print("KeyError")
            LOG.debug("best entity = %s" % best_entity)
            return best_entity

    #
    # checking the entity attributes to be used in the response dialog.
    #

    def find_entity_attr(self, entity):
        json_data = self._get_state()

        if json_data:
            for attr in json_data:
                if attr['entity_id'] == entity:
                    entity_attrs = attr['attributes']
                    try:
                        if attr['entity_id'].startswith('light.'):
                            # Not all lamps do have a color
                            unit_measur = entity_attrs['brightness']
                        else:
                            unit_measur = entity_attrs['unit_of_measurement']
                    except KeyError:
                        unit_measur = None
                    # IDEA: return the color if available
                    # TODO: change to return the whole attr dictionary =>
                    # free use within handle methods
                    sensor_name = entity_attrs['friendly_name']
                    sensor_state = attr['state']
                    entity_attr = {
                        "unit_measure": unit_measur,
                        "name": sensor_name,
                        "state": sensor_state
                    }
                    return entity_attr
        return None

    #def execute_service(self, domain, service, data):
    def execute_service(self, cmd, device=None, value=None):
        #TODO add code from _get_state for SSL handling
        BASE_URL = "%s?" % self.url
        command = "cmd={}".format(cmd)
        if device is not None:
            command += "%20{}".format(device)
        if value is not None:
            command += "%20{}".format(value)
        cmd_req = BASE_URL + command + "&fwcsrf=" + self.__get_csrf()
        LOG.debug("cmd_req = %s" % cmd_req)

        req = get(cmd_req)
        return req

    def find_component(self, component):
        """Check if a component is loaded at the Fhem-Server"""
        if self.ssl:
            req = get("%s/api/components" %
                      self.url, headers=self.headers, verify=self.verify,
                      timeout=TIMEOUT)
        else:
            req = get("%s/api/components" % self.url, headers=self.headers,
                      timeout=TIMEOUT)

        if req.status_code == 200:
            return component in req.json()

    def get_device(self, name, value):
        #retrieve a FHEM-device by name=value
        LOG.debug("retrieve a FHEM-device by {}={}".format(name,value))
        req = self.execute_service("jsonlist2","{}={}&XHR=1".format(name,value))

        if req.status_code == 200:
            device = req.json()
        else:
            return None

        if device['totalResultsReturned']==1:
            #LOG.debug("device found: %s" % device['Results'][0])
            return device['Results'][0]
        else:
            return None

    def engage_conversation(self, utterance):
        """Engage the conversation component (Babble?) at the Fhem server
        Attributes:
            utterance    raw text message to be processed
        Return:
            Dict answer by Fhem server
            { 'speech': textual answer,
              'extra_data': ...}
        """
        data = {
            "text": utterance
        }
        if self.ssl:
            return post("%s/api/conversation/process" % (self.url),
                        headers=self.headers,
                        data=json.dumps(data),
                        verify=self.verify,
                        timeout=TIMEOUT
                        ).json()['speech']['plain']
        else:
            return post("%s/api/conversation/process" % (self.url),
                        headers=self.headers,
                        data=json.dumps(data),
                        timeout=TIMEOUT
                        ).json()['speech']['plain']
