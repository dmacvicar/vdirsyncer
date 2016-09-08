# -*- coding: utf-8 -*-

import collections
import logging
import os

import mailbox
import dateutil.parser

from .base import Item, Storage
from .. import exceptions
from ..utils import expand_path
from ..utils.compat import iteritems
from ..utils.vobject import split_collection
from ..utils.vobject import _Component

logger = logging.getLogger(__name__)


MAILDIR_STORAGE_PARAMETERS = '''
    :param path: Maildir path.
'''


class MaildirStorage(Storage):
    __doc__ = '''
    Use events stored as part of mails inside a maildir
    directory.
    ''' + MAILDIR_STORAGE_PARAMETERS + '''

    A simple example::

        [pair holidays]
        a = holidays_local
        b = holidays_maildir

        [storage holidays_local]
        type = filesystem
        path = ~/.config/vdir/calendars/holidays/
        fileext = .ics

        [storage holidays_maildir]
        type = maildir
        path = /home/bob/Mail/Calendar
    '''
    storage_name = 'maildir'
    read_only = True
    _repr_attributes = ('path',)
    _items = None

    def __init__(self, path, encoding='utf-8', **kwargs):
        super(MaildirStorage, self).__init__(**kwargs)
        path = os.path.abspath(expand_path(path))

        self.path = path
        self.encoding = encoding
        self._at_once = False

        collection = kwargs.get('collection')
        if collection is not None:
            self.path = os.path.join(self.path, collection)

    def list(self):
        self._items = collections.OrderedDict()

        mb = mailbox.Maildir(self.path)
        for key, message in mb.iteritems():
            if not message.is_multipart():
                continue
            for part in message.get_payload():
                if 'text/calendar' not in part['content-type']:
                    continue

                for item in split_collection(part.get_payload()):
                    item = Item(item)
                    etag = item.hash
                    if item.ident in self._items:
                        old = _Component(
                            'TEMP',
                            self._items[item.ident][0].raw.splitlines(), [])
                        new = _Component(
                            'TEMP',
                            item.raw.splitlines(), [])

                        last_modified_old = dateutil.parser.parse(
                            old.get('LAST-MODIFIED'))
                        last_modified_new = dateutil.parser.parse(
                            new.get('LAST-MODIFIED'))
                        if last_modified_new > last_modified_old:
                            self._items[item.ident] = item, etag
                    else:
                        self._items[item.ident] = item, etag

        return ((href, etag) for href, (item, etag) in iteritems(self._items))

    def get(self, href):
        if self._items is None or not self._at_once:
            self.list()

        try:
            return self._items[href]
        except KeyError:
            raise exceptions.NotFoundError(href)

