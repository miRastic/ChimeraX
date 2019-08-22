# vim: set expandtab shiftwidth=4 softtabstop=4:

# === UCSF ChimeraX Copyright ===
# Copyright 2016 Regents of the University of California.
# All rights reserved.  This software provided pursuant to a
# license agreement containing restrictions on its disclosure,
# duplication and use.  For details see:
# http://www.rbvi.ucsf.edu/chimerax/docs/licensing.html
# This notice must be embedded in or attached to all copies,
# including partial copies, of the software or any revisions
# or derivations thereof.
# === UCSF ChimeraX Copyright ===

from chimerax.core.toolshed import ProviderManager
class ItemsInspection(ProviderManager):
    """Manager for options needed to inspect items"""

    def __init__(self, session):
        self.session = session
        self._item_info = {}
        from chimerax.core.triggerset import TriggerSet
        self.triggers = TriggerSet()
        self.triggers.add_trigger("inspection items changed")

    @property
    def item_types(self):
        return list(self._item_info.keys())

    def item_info(self, item_type):
        info = self._item_info[item_type]
        if not isinstance(info, (list, tuple)):
            info = self._item_info[item_type] = info.run_provider(self.session, item_type, self)
        return info[:]

    def add_provider(self, bundle_info, name, **kw):
        """ The provider's run_provider method should return a 2-tuple.  The first member of the tuple
            should be a list of chimerax.ui.options classes that can be instantiated to inspect various
            properties of the item type.  The instances should have a "command_format" attribute that is
            a string with a single '%s', into which the "end user" inspector will interpolate command-
            line-target text (e.g., 'sel').  The result should be executable as a command when the option's
            value is changed to in turn accomplish the change in the data itself.  The second member of
            the tuple provides information on when the options need updating from external changes.
            It is a list of (trigger set, trigger name, boolean func) tuples for triggers that fire
            when relevant changes occur.  The boolean function will be called with the trigger's data
            and should return True when items of the relevant type have been modified.

            If an option controls a particular attribute of the item then the option's 'attr_name'
            attribute should be set to that.  This will cause the option's balloon help to automatically
            add information about the attribute name to the bottom of the help balloon.  If the
            values of the attributes need explanation (e.g. they're an integer enumeration with
            semantic meaning), then set the option's 'attr_values_balloon' attribute to whatever
            additional text you would want to add to the bottom of the balloon.

            Since any inspector would have no idea what the correct default is to provide to the
            option constructor, the option needs to have its 'default' class attribute set in the
            class definition (unless a default of None is acceptable, which is what is provided to
            the constructor).
        """
        self._item_info[name] = bundle_info

    def end_providers(self):
        self.triggers.activate_trigger("inspection items changed", self)
