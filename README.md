# hass-environment-canada

This is a config_flow (aka GUI-based) Environment Canada integration. The plan is to replace the existing Environment Canada integration (YAML config file based)
with this one. Expect this code to be submitted to Home Assistant to become part of their release something around October 2021.

We are encouraging people to try this integration as a `custom_components` installation. The code is functionally complete and just cleanup and bug fixes are
happening now.

Note that many of the sensors are disabled by default. This is the normal pattern for weather integrations in HA and is done so as to not pollute the name space.
They can be enabled in Configuration -> Entities.

Also note that the dialogues for configuration have "funky" titles/labels. For the most part you should be able to figure out the purpose of the data entry fields.
The labels will be correct for the final integration in HA. They are incorrect now as `custom_components` do not support keyed labels.

When the integration with Home Assistant is complete this repo will be archived and no longer supported.
