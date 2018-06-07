# Home Assistant Skill for Mycroft

[![Stories in Ready](https://badge.waffle.io/btotharye/mycroft-homeassistant.svg?label=ready&title=Ready)](http://waffle.io/btotharye/mycroft-homeassistant)
[![Build Status](https://travis-ci.org/btotharye/mycroft-homeassistant.svg?branch=master)](https://travis-ci.org/btotharye/mycroft-homeassistant)
[![Coverage Status](https://coveralls.io/repos/github/btotharye/mycroft-homeassistant/badge.svg?branch=master)](https://coveralls.io/github/btotharye/mycroft-homeassistant?branch=master)
[![Discord](https://img.shields.io/discord/348442860510642176.svg)](https://discord.gg/Xnn89dB)



based off the original code from https://github.com/btotharye/mycroft-homeassistant for Home Assistant, spun off my own version for Fhem.

Make sure you have your Fhem settings filled out on home.mycroft.ai.

Testrunner tests are now setup as well to test intents.  

This is a skill to add [Fhem](https://fhem.de) support to
[Mycroft](https://mycroft.ai). Currently is support turning on and off several
entity types (`light`, `switch`, `scene`, `groups` and `input_boolean`).

## Installation
Before installation ensure you have python-dev package installed for your OS.  For debian this would be `apt-get install python-dev` it is required for the levenstein package.

Should be able to install this now via just saying `Hey Mycroft, install skill fhem` it will then confirm if you want to install it and say yes and you are good to go.

Can also be installed via `msm install https://github.com/domcross/fhem-skill.git`


## Configuration
This skill utilizes the skillsettings.json file which allows you to configure this skill via home.mycroft.ai after a few minutes of having the skill installed you should see something like below in the https://home.mycroft.ai/#/skill location:

Fill this out with your appropriate Fhem information and hit save.

![Screenshot](screenshot.JPG?raw=true)

## Usage

Say something like "Hey Mycroft, turn on living room lights". Currently available commands
are "turn on" and "turn off". Matching to Fhem entity names is done by scanning
the Fhem API and looking for the closest matching alias name. The matching is fuzzy (thanks
to the `fuzzywuzzy` module) so it should find the right entity most of the time, even if Mycroft
didn't quite get what you said.  I have further expanded this to also look at groups as well as lights.  This way if you say turn on the office light, it will do the group and not just 1 light, this can easily be modified to your preference by just removing group's from the fuzzy logic in the code.


Example Code:
So in the code in this section you can just remove group, etc to your liking for the lighting.  I will eventually set this up as variables you set in your config file soon.

```
def handle_lighting_intent(self, message):
        entity = message.data["Entity"]
        action = message.data["Action"]
        LOGGER.debug("Entity: %s" % entity)
        LOGGER.debug("Action: %s" % action)
        ha_entity = self.ha.find_entity(entity, ['group','light', 'switch', 'scene', 'input_boolean'])
        if ha_entity is None:
            #self.speak("Sorry, I can't find the Home Assistant entity %s" % entity)
            self.speak_dialog('homeassistant.device.unknown', data={"dev_name": ha_entity['dev_name']})
            return
        ha_data = {'entity_id': ha_entity['id']}
```


## Supported Phrases/Entities
Currently the phrases are:
* Hey Mycroft, turn on office (turn on the group office)
* Hey Mycroft, turn on office light (to turn on the light named office)
* Hey Mycroft, activate Bedtime (Bedtime is an automation)
* Hey Mycroft, turn on Movietime (Movietime is a scene)
* Hey Mycroft, status of thermostat (For sensors in homeassistant)
* Hey Mycroft, locate/where brian (Brian is a device tracker object)
* Hey Mycroft, what is the current living room temp
* Hey Mycroft, what is the current season



## TODO
 * Script intents processing
 * New intent for opening/closing cover entities
 * New intent for locking/unlocking lock entities (with added security?)
 * New intent for thermostat values, raising, etc.
 * New intent to handle multimedia/kodi

## In Development
* Climate and Weather intents

## Contributing

All contributions welcome:

 * Fork
 * Write code
 * Submit merge request

## Licence

See [`LICENCE`](https://gitlab.com/robconnolly/mycroft-home-assistant/blob/master/LICENSE).
