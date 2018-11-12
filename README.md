# FHEM Skill for Mycroft

based off the original code from https://github.com/btotharye/mycroft-homeassistant for Home Assistant, I have spun off my own version for Fhem.

Make sure you have your Fhem settings filled out on home.mycroft.ai.

This is a skill to add [Fhem](https://fhem.de) support to
[Mycroft](https://mycroft.ai). Currently is support turning on and off several entity types (`light`, `switch`, `outlet`), changing temperature (`thermostat`) and get status information (`sensor`, `thermometer`).

## Installation
Before installation ensure you have python-dev package installed for your OS.  For debian this would be `apt-get install python-dev` it is required for the levenstein package.

This skill can be installed via `msm install https://github.com/domcross/fhem-skill.git`


## Configuration
This skill utilizes the skillsettings.json file which allows you to configure this skill via home.mycroft.ai after a few minutes of having the skill installed you should see something like below in the https://home.mycroft.ai/#/skill location:

Fill this out with your appropriate Fhem information and hit save.
(Note: SSL options are currently not supported.)

![Screenshot](screenshot.JPG?raw=true)

## Usage

Say something like "Hey Mycroft, turn on living room lights". Currently available commands are "turn (on|off) <device>" and "status <device>". 
Matching to Fhem entity names is done by scanning the Fhem API and looking for the closest matching device ID or alias name. The matching is fuzzy (thanks to the `fuzzywuzzy` module) so it should find the right entity most of the time, even if Mycroft didn't quite get what you said.  

## Supported Phrases/Entities
Currently the phrases are:
* Hey Mycroft, turn on office light (to turn on the light named office)
* Hey Mycroft, status of thermostat (For sensors in homeassistant)
* Hey Mycroft, what is the current living room temp
* Hey Mycroft, set thermostat livingroom to 20 degrees

## TODO
 * Script intents processing
 * New intent for opening/closing cover entities
 * New intent for locking/unlocking lock entities (with added security?)
 * New intent to handle multimedia/kodi
 * New intent for tracking residents status (absent)

## In Development
* Climate and Weather intents

## Contributing

All contributions welcome:

 * Fork
 * Write code
 * Submit merge request

## Licence

See [`LICENCE`](https://apache.org/licenses/LICENSE-2.0).
