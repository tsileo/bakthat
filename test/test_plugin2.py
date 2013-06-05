from bakthat.plugin import Plugin
from bakthat.models import Backups


class MyBackups(Backups):
    @classmethod
    def my_custom_method(self):
        return True


class ChangeModelPlugin(Plugin):
    """ A basic plugin implementation. """
    def activate(self):
        global Backups
        self.log.info("Replace Backups")
        Backups = MyBackups
