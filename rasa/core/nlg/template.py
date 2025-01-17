import copy
import logging
from collections import defaultdict
from rasa.cli.utils import bcolors

from rasa.core.trackers import DialogueStateTracker
from typing import Text, Any, Dict, Optional, List

from rasa.core.nlg.generator import NaturalLanguageGenerator
from rasa.core.nlg.interpolator import interpolate_text, interpolate

logger = logging.getLogger(__name__)

class InvalidNLGRequest(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return bcolors.FAIL + self.message + bcolors.ENDC

class TemplatedNaturalLanguageGenerator(NaturalLanguageGenerator):
    """Natural language generator that generates messages based on templates.

    The templates can use variables to customize the utterances based on the
    state of the dialogue."""

    def __init__(self, templates: Dict[Text, Dict[Text, List[List[Dict[Text, Any]]]]]) -> None:
        self.templates = templates

    def _templates_for_utter_action(self, utter_action, output_channel):
        """Return array of templates that fit the channel and action."""

        channel_templates = []
        default_templates = []

        for template in self.templates[utter_action]:
            if template.get("channel") == output_channel:
                channel_templates.append(template)
            elif not template.get("channel"):
                default_templates.append(template)

        # always prefer channel specific templates over default ones
        if channel_templates:
            return channel_templates
        else:
            return default_templates

    # noinspection PyUnusedLocal
    def _random_template_for(
        self, utter_action: Text, output_channel: Text
    ) -> Optional[Dict[Text, Any]]:
        """Select random template for the utter action from available ones.

        If channel-specific templates for the current output channel are given,
        only choose from channel-specific ones.
        """
        import numpy as np

        if utter_action in self.templates:
            suitable_templates = self._templates_for_utter_action(
                utter_action, output_channel
            )

            if suitable_templates:
                return np.random.choice(suitable_templates)
            else:
                return None
        else:
            return None

    async def generate(
        self,
        template_name: Text,
        tracker: DialogueStateTracker,
        output_channel: Text,
        **kwargs: Any
    ) -> Optional[Dict[Text, Any]]:
        """Generate a response for the requested template."""

        filled_slots = tracker.current_slot_values()
        return self.generate_from_bf_template(
            template_name, filled_slots, output_channel, **kwargs
        )

    def generate_from_bf_template(
        self,
        template_name: Text,
        filled_slots: Dict[Text, Any],
        output_channel: Text,
        **kwargs: Any
    ) -> Optional[Dict[Text, Any]]:
    
        language = kwargs.get("language", None)
        if not language:
            raise InvalidNLGRequest("Generator expected a language to return template")
        if template_name not in self.templates:
            return None
        
        return [self._fill_template(
            copy.deepcopy(template), filled_slots, **kwargs
        ) for template in self.templates[template_name][language]]

    def generate_from_slots(
        self,
        template_name: Text,
        filled_slots: Dict[Text, Any],
        output_channel: Text,
        **kwargs: Any
    ) -> Optional[Dict[Text, Any]]:
        """Generate a response for the requested template."""

        # Fetching a random template for the passed template name
        r = copy.deepcopy(self._random_template_for(template_name, output_channel))
        # Filling the slots in the template and returning the template
        if r is not None:
            return self._fill_template(r, filled_slots, **kwargs)
        else:
            return None

    def _fill_template(
        self,
        template: Dict[Text, Any],
        filled_slots: Optional[Dict[Text, Any]] = None,
        **kwargs: Any
    ) -> Dict[Text, Any]:
        """"Combine slot values and key word arguments to fill templates."""

        # Getting the slot values in the template variables
        template_vars = self._template_variables(filled_slots, kwargs)

        keys_to_interpolate = [
            "text",
            "image",
            "custom",
            "button",
            "attachment",
            "quick_replies",
        ]
        if template_vars:
            for key in keys_to_interpolate:
                if key in template:
                    template[key] = interpolate(template[key], template_vars)
        return template

    @staticmethod
    def _template_variables(
        filled_slots: Dict[Text, Any], kwargs: Dict[Text, Any]
    ) -> Dict[Text, Any]:
        """Combine slot values and key word arguments to fill templates."""

        if filled_slots is None:
            filled_slots = {}

        # Copying the filled slots in the template variables.
        template_vars = filled_slots.copy()
        template_vars.update(kwargs)
        return template_vars
