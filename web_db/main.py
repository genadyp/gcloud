
import webapp2
from google.appengine.ext import ndb
from google.appengine.api import taskqueue

from google.appengine.ext import deferred
import time

""" Constants """
    
DEFER_COUNTDOWN = 1
DEFER_WAIT = .500

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

def put_value(name, value):
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

def unset_name(name):
    latest = get_latest(name)
    none = WebDbEntry(name=name, value=None, is_active=True)
    none.previous_key = latest.key.urlsafe() if latest else None
    none.put()

    if latest:
        latest.is_active = False
        latest.next_key = none.key.urlsafe()
        latest.put()

def undo_value(key):
    latest = key.get()

    if latest and latest.previous_key:
        latest.is_active = False
        latest.put()

        previous_key = ndb.Key(urlsafe=latest.previous_key)
        previous = previous_key.get()
        previous.is_active = True
        previous.put()

def redo_value(key):
    latest = key.get()
    if latest and latest.next_key:
        latest.is_active = False
        latest.put()

        next_key = ndb.Key(urlsafe=latest.next_key)
        next_entry = next_key.get()
        next_entry.is_active = True
        next_entry.put()

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

        response = get_latest(name)
        value = response.value if response else None

        self.response.headers['Content-Type'] = 'text/plain'
        self.response.write('%s = %s' % (name, value))

class SetHandler(webapp2.RequestHandler):
    def put(self):
        name = self.request.get("name")
        value = self.request.get("value")

        deferred.defer(put_value, name, value, _countdown=DEFER_COUNTDOWN)

        # TODO: Do we actually need it??
        # Should we return response immediately??
        while True:
            current = get_latest(name)
            if current and current.value == value:
                break
            else:
                time.sleep(DEFER_WAIT)

        self.response.headers['Content-Type'] = 'text/plain'
        self.response.write('%s = %s' % (name, value))

class UnsetHandler(webapp2.RequestHandler):
    def delete(self):
        name = self.request.get("name")

        deferred.defer(unset_name, name, _countdown=DEFER_COUNTDOWN)
       
        # TODO: Do we actually need it?? 
        # Should we return response immediately??
        while True:
            current = get_latest(name)
            if current and current.value == None:
                break
            else:
                time.sleep(DEFER_WAIT)

        self.response.headers['Content-Type'] = 'text/plain'
        self.response.write('%s = %s' % (name, 'None'))

class NumEqualToHandler(webapp2.RequestHandler):
    def get(self):
        value = self.request.get("value")
        # NOTICE: suppose that None is an illegal value
        count = WebDbEntry.query(WebDbEntry.value == value, WebDbEntry.is_active == True).count() if value != None else 0

        self.response.headers['Content-Type'] = 'text/plain'
        self.response.write(count)


class UndoHandler(webapp2.RequestHandler):
    def put(self):
        latest = get_latest(None)
        name = latest.name
        if latest and latest.previous_key:
            deferred.defer(undo_value, latest.key, _countdown=DEFER_COUNTDOWN)

            while True:
                current = get_latest(name)
                if current.key != latest.key:
                    break
                else:
                    time.sleep(DEFER_WAIT)

            self.response.headers['Content-Type'] = 'text/plain'
            self.response.write('%s = %s' % (name, current.value))
        else:
            self.response.headers['Content-Type'] = 'text/plain'
            self.response.write('NO COMMANDS')

class RedoHandler(webapp2.RequestHandler):
    def put(self):
        latest = get_latest(None)
        name = latest.name
        if latest and latest.next_key:
            deferred.defer(redo_value, latest.key, _countdown=DEFER_COUNTDOWN)

            while True:
                current = get_latest(name)
                if current.key != latest.key:
                    break
                else:
                    time.sleep(DEFER_WAIT)


            self.response.headers['Content-Type'] = 'text/plain'
            self.response.write('%s = %s' % (name, current.value))
        else:
            self.response.headers['Content-Type'] = 'text/plain'
            self.response.write('NO COMMANDS')

class EndHandler(webapp2.RequestHandler):
    def delete(self):
        keys = WebDbEntry.query().fetch(keys_only=True)
        ndb.delete_multi(keys)

        self.response.headers['Content-Type'] = 'text/plain'
        self.response.write('CLEANED')

""" App """

app = webapp2.WSGIApplication([
    ('/get',    GetHandler),
    ('/set',     SetHandler),
    ('/unset', UnsetHandler),
    ('/numequalto', NumEqualToHandler),
    ('/undo',      UndoHandler),
    ('/redo',      RedoHandler),
    ('/end',    EndHandler)
], debug=False)

