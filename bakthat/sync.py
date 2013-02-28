# -*- encoding: utf-8 -*-
import logging
import bakthat
from bakthat.conf import config, DEFAULT_DESTINATION, DEFAULT_LOCATION

try:
    import requests
except ImportError, ie:
    raise Exception("You must install requests module in order to use sync.")
import json


class BakSyncer:
    """Helper to synchronize change on a backup set via a REST API.

    :type api_url: str
    :param api_url: Base API URL

    :type auth: tuple
    :param auth: A tuple/list with credentials (username, password)

    """
    def __init__(self, api_url, auth=None):
        self.api_url = api_url
        self.auth = auth
        self.request_kwargs = {}
        if self.auth:
            self.request_kwargs["auth"] = self.auth
        self.request_kwargs["headers"] = {'content-type': 'application/json'}
        self.resource_fmt = self.api_url + "/{0}"

    def post(self, data={}):
        """Post/create new backup.

        :type data: dict
        :param data: Backup dict

        """
        r_kwargs = self.request_kwargs.copy()
        r_kwargs.update({"data": json.dumps(data)})
        r = requests.post(self.api_url, **r_kwargs)
        if r.status_code != 200:
            log.error("An error occured during sync: {0}".format(r.text))

    def delete(self, backup):
        """Delete a backup.

        :type backup: str
        :param backup: Full backup stored filename.

        """
        r = requests.delete(self.resource_fmt.format(backup), **self.request_kwargs)
        if r.status_code != 200:
            log.error("An error occured during sync: {0}".format(r.text))
