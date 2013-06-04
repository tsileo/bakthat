import time

from bakthat.plugin import Plugin


class TestPlugin(Plugin):
    """ A basic plugin implementation. """
    def activate(self):
        self.start = {}
        self.stop = {}
        self.before_backup += self.before_backup_callback
        self.on_backup += self.on_backup_callback

    def before_backup_callback(self, session_id):
        self.start[session_id] = time.time()
        self.log.info("before_backup {0}".format(session_id))

    def on_backup_callback(self, session_id, backup):
        self.stop[session_id] = time.time()
        self.log.info("on_backup {0} {1}".format(session_id, backup))
        self.log.info("Job duration: {0}s".format(self.stop[session_id] - self.start[session_id]))
