# Copyright 2016 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions an        # key = WebDbKey(name=name).key
        # response = WebDbEntry.get_by_id(key)d
# limitations under the License.

import webapp2
from google.appengine.ext import ndb
from google.appengine.api import taskqueue

""" NDB utils """

def get_latest(name):
    if name:
        response = WebDbEntry.query(
            WebDbEntry.name == name, WebDbEntry.is_active == True).order(-WebDbEntry.datetime).fetch(limit=1)
    else:
        response = WebDbEntry.query(WebDbEntry.is_active == True).order(-WebDbEntry.datetime).fetch(limit=1)

    return response[0] if response else None

def get_all(name, limit):
    if limit:
        return WebDbEntry.query(WebDbEntry.name == name).order(-WebDbEntry.datetime).fetch(limit = limit)
    else:
        return WebDbEntry.query(WebDbEntry.name == name).order(-WebDbEntry.datetime).fetch()


def disactivate(entry):
    entry.is_active = False
    entry.put()

def disactivate_latest(name):
    latest = get_latest(name)
    if latest:
        disactivate(latest)

def activate(entry):
    entry.is_active = True
    entry.put()        

""" Model """

class WebDbEntry(ndb.Model):
    name = ndb.StringProperty(required=True)
    value = ndb.StringProperty()
    is_active = ndb.BooleanProperty(required=True)
    previous_key = ndb.StringProperty()
    next_key = ndb.StringProperty()
    datetime = ndb.DateTimeProperty(auto_now=True)



""" Handlers """

class GetHandler(webapp2.RequestHandler):
    def get(self):
        name = self.request.get("name")

        # key = WebDbKey(name=name).key
        # response = WebDbEntry.get_by_id(key)

        # response = WebDbEntry.get_by_id(name)
        
        # response = WebDbEntry.query(WebDbEntry.name == name).order(-WebDbEntry.date).fetch(limit=1)
        # value = response[0].value if response else None

        response = get_latest(name)
        value = response.value if response else None

        self.response.headers['Content-Type'] = 'text/plain'
        self.response.write('%s = %s' % (name, value))

class SetHandler(webapp2.RequestHandler):
    def put(self):
        name = self.request.get("name")
        value = self.request.get("value")

        # key = WebDbKey(name=name).key
        # model = WebDbEntry(key=key, value=value)

        # model = WebDbEntry(value=value)
        # model.key = ndb.Key(WebDbEntry, name)

        # disactivate_latest(name)
        latest = get_latest(name)

        if not latest:
            latest = WebDbEntry(name=name, value=None, is_active=True)       
            latest.put()

        entry = WebDbEntry(name=name, value=value, is_active=True)
        entry.previous_key = latest.key.urlsafe()
        entry.next_key = None
        entry.is_active = True
        key = entry.put()

        latest.is_active = False
        latest.next_key = key.urlsafe()
        latest.put()

        self.response.headers['Content-Type'] = 'text/plain'
        self.response.write('%s = %s' % (name, value))

class UnsetHandler(webapp2.RequestHandler):
    def delete(self):
        name = self.request.get("name")

        # key = WebDbKey(name=name).key
        # response = WebDbEntry.get_by_id(key)
        # key = ndb.Key(WebDbEntry, name)
        # key.delete()
        # response = WebDbEntry.query(WebDbEntry.name == name).fetch()

        # keys = WebDbEntry.query(WebDbEntry.name == name).fetch(keys_only=True)
        # ndb.delete_multi(keys)

        # disactivate_latest(name)
        # none_entry = WebDbEntry(name=name, value=None, is_active=False)
        # none_entry.put()

        latest = get_latest(name)
        none = WebDbEntry(name=name, value=None, is_active=True)
        none.previous_key = latest.key.urlsafe() if latest else None
        none.put()

        if latest:
            latest.is_active = False
            latest.next_key = none.key.urlsafe()
            latest.put()

        self.response.headers['Content-Type'] = 'text/plain'
        self.response.write('%s = %s' % (name, 'None'))

class NumEqualToHandler(webapp2.RequestHandler):
    def get(self):
        value = self.request.get("value")
        # NOTICE: suppose that None is illegal value
        count = WebDbEntry.query(WebDbEntry.value == value, WebDbEntry.is_active == True).count() if value != None else 0

        self.response.headers['Content-Type'] = 'text/plain'
        self.response.write(count)


class UndoHandler(webapp2.RequestHandler):
    def put(self):
        latest_entry = get_latest(None)
        if latest_entry and latest_entry.previous_key:
            name = latest_entry.name

            latest_entry.is_active = False
            latest_entry.put()

            previous_key = ndb.Key(urlsafe=latest_entry.previous_key)
            previous = previous_key.get()
            previous.is_active = True
            previous.put()

            # entries = get_all(name, 2)
            # disactivate(latest_entry)

            # if len(entries) == 2:
            #     activate(entries[1])
            #     value = entries[1].value
            # else:
            #     none_entry = WebDbEntry(name=name, value=None, is_active=False)
            #     none_entry.put()

            self.response.headers['Content-Type'] = 'text/plain'
            self.response.write('%s = %s' % (name, previous.value))
        else:
            self.response.headers['Content-Type'] = 'text/plain'
            self.response.write('NO COMMANDS')

class RedoHandler(webapp2.RequestHandler):
    def put(self):
        latest_entry = get_latest(None)
        if latest_entry and latest_entry.next_key:
            name = latest_entry.name

            latest_entry.is_active = False
            latest_entry.put()

            next_key = ndb.Key(urlsafe=latest_entry.next_key)
            next_entry = next_key.get()
            next_entry.is_active = True
            next_entry.put()

            self.response.headers['Content-Type'] = 'text/plain'
            self.response.write('%s = %s' % (name, next_entry.value))
        else:
            self.response.headers['Content-Type'] = 'text/plain'
            self.response.write('NO COMMANDS')

class EndHandler(webapp2.RequestHandler):
    def delete(self):
        keys = WebDbEntry.query().fetch(keys_only=True)
        ndb.delete_multi(keys)

        self.response.headers['Content-Type'] = 'text/plain'
        self.response.write('CLEANED')

app = webapp2.WSGIApplication([
    ('/get',    GetHandler),
    ('/set',     SetHandler),
    ('/unset', UnsetHandler),
    ('/numequalto', NumEqualToHandler),
    ('/undo',      UndoHandler),
    ('/redo',      RedoHandler),
    ('/end',    EndHandler)
], debug=False)
