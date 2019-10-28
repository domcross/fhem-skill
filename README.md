# FHEM Skill for Mycroft
This is a skill to add [Fhem](https://fhem.de) support to
[Mycroft](https://mycroft.ai). Currently supported is turning on and off several entity types (`light`, `switch`, `outlet`), changing temperature (`thermostat`) and get status information (`sensor`, `thermometer`). You can also check if a person is present (that is represented by a Fhem-device of type ROOMMATE).

Make sure you have your Fhem settings filled out on home.mycroft.ai.

## Installation
Before installation ensure you have python-dev package installed for your OS.  For debian this would be `apt-get install python-dev` it is required for the levenstein package.

This skill can be installed via `mycroft-msm install https://github.com/domcross/fhem-skill.git`

## Configuration
This skill utilizes the skillsettings.json file which allows you to configure this skill via home.mycroft.ai after a few minutes of having the skill installed you should see something like below in the https://home.mycroft.ai/#/skill location:

Fill this out with your appropriate Fhem information and hit save.
(Note: SSL options are currently not supported.)

![Screenshot](skill-settings.jpg?raw=true)


When using option "Use Mycroft device description as location" don't forget to enter the location info in home.mycroft.ai > <username> > devices

![Screenshot](device-info.jpg?raw=true)

## FHEM Configuration
you have to set up the appropriate genericDeviceType under Fhem. you add the following under global userattr:
'genericDeviceType:thermometer,thermostat,contact,garage,window,lock,security,ignore,switch,outlet,light,blind'


## Usage
Say something like "Hey Mycroft, turn on the lights in the living room". Currently available commands are "turn (on|off) *device*" and "status *device*".
Matching the Fhem device is done in following order:
* check if given room has exactly one device of desired type (e.g. only one "thermostat")
* search for closest matching device ID or alias name.
* prefer devices that are in the desired room

The matching is fuzzy (thanks to the `fuzzywuzzy` module) so it should find the right device most of the time, even if Mycroft didn't quite get what you said.
Nevertheless this is not perfect and sometime the wrong devices are triggered. Your feedback on this with examples is highly welcomed.

## Supported Phrases/Entities
Currently the phrases are:
* Hey Mycroft, turn on office light  (to turn on the light named office)
* Hey Mycroft, status of weather station (for a device named "weather station")
* Hey Mycroft, set thermostat in the livingroom to 20 degrees
* Hey Mycroft, where is *name of person*
* Hey Mycroft, open shades in the bedroom

## TODO
 * Optimize retrieval of devices
 * New intents (light scenes and dimmer control, shutters and door locks, etc.)
 * ...?

## Contributing
All contributions welcome:
 * Fork
 * Write code
 * Submit merge request

## Licence
See [`LICENCE`](https://apache.org/licenses/LICENSE-2.0).
