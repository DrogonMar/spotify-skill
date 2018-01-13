import time
import datetime

from mycroft.skills.core import MycroftSkill, intent_handler
from mycroft.util.log import LOG
from adapt.intent import IntentBuilder

import mycroft.client.enclosure.display_manager as DisplayManager

import spotipy

from mycroft.api import DeviceApi
from requests import HTTPError

class SpotifyConnect(spotipy.Spotify):
    def get_devices(self):
        LOG.debug('getting devices')
        return self._get('me/player/devices')

    def play(self, device, playlist):
        tracks = self.user_playlist_tracks(playlist['owner']['id'],
                                           playlist['id'])
        uris = [t['track']['uri'] for t in tracks['items']]
        data = {}
        data['uris'] = uris
        path = 'me/player/play?device_id={}'.format(device)
        self._put(path, payload=data)


    def pause(self, device):
        """ Pause user's playback.

            Parameters:
                - device_id - device target for playback
        """
        LOG.info('Pausing spotify playback')
        try:
            self._put('me/player/pause?device_id={}'.format(device))
        except Exception as e:
            LOG.error(e)


class SpotifySkill(MycroftSkill):
    def __init__(self):
        super(SpotifySkill, self).__init__()
        self.index = 0
        self.spotify = None
        self.spoken_goto_home = False

    def initialize(self):
        self.schedule_repeating_event(self.load_credentials,
                                      datetime.datetime.now(), 60,
                                      name='get_creds')


    def load_credentials(self):
        """ Repeating function trying to retrieve credentials from the
            backend.

            When credentials are found the skill connects
        """
        try:
            token = DeviceApi().get_oauth_token(1)
            self.spotify = SpotifyConnect(auth=token['access_token'])
        except HTTPError:
            pass

        if self.spotify:
            # Spotfy connection worked, cancel recurring event and
            # prepare for usage
            # If not able to authorize, the method will be repeated after 60
            # seconds
            self.cancel_scheduled_event('get_creds')
            self.get_playlists()
        elif not self.spoken_goto_home:
            # First time loading the skill speak a request to go to home
            # to authorize
            self.speak_dialog('authorize')
            self.spoken_goto_home = True

    def get_playlists(self):
        """
            Fetch user's playlists.
        """
        self.playlists = {}
        playlists = self.spotify.current_user_playlists().get('items', [])
        for p in playlists:
            self.playlists[p['name']] = p
            self.register_vocabulary(p['name'], 'PlaylistKeyword')

    @intent_handler(IntentBuilder('PlayPlaylistIntent')\
        .require('PlayKeyword')\
        .require('PlaylistKeyword')\
        .build())
    def play_playlist(self, message):
        """
            Play user playlist.
        """
        if self.spotify is None:
            self.speak('Not authorized')
            return

        p = message.data.get('PlaylistKeyword')
        device = self.spotify.get_devices()
        if device and len(device) > 0:
            dev_id = device['devices'][0]['id']
            LOG.debug(dev_id)
            self.speak_dialog('listening_to', data={'tracks': p})
            time.sleep(2)
            self.spotify.play(dev_id, self.playlists[p])
            #self.show_notes()

    def show_notes(self):
        """ show notes, HA HA """
        self.schedule_repeating_event(self._update_notes,
                                      datetime.datetime.now(), 2,
                                      name='dancing_notes')

    def display_notes(self):
        """
            Start timer thread displaying notes on the display.
        """
        pass

    def clear_display(self):
        """ Clear display. """

        self.enclosure.mouth_display(img_code="HIAAAAAAAAAAAAAA",
                                     refresh=False)
        self.enclosure.mouth_display(img_code="HIAAAAAAAAAAAAAA",
                                     x=24, refresh=False)

    def draw_notes(self, index):
        """ Draw notes on display. """

        notes = [['IIAEAOOHGAGEGOOHAA', 'IIAAACAHPDDADCDHPD'],
                 ['IIAAACAHPDDADCDHPD', 'IIAEAOOHGAGEGOOHAA']]

        #  draw notes
        for pos in range(4):
            self.enclosure.mouth_display(img_code=notes[index][pos % 2],
                                         x=pos * 8,
                                         refresh=False)

    def _update_notes(self):
        """
            Repeating event updating the display.
        """
        if self._should_display_notes():
            self.draw_notes(self.index)
            self.index = ((self.index + 1) % 2)

    def stop(self):
        #self.remove_event('dancing_notes')

        self.enclosure.reset()
        device = self.spotify.get_devices()
        if device:
            self.enclosure.reset()
            dev_id = device['devices'][0]['id']
            self.spotify.pause(dev_id)

    def _should_display_notes(self):
        _get_active = DisplayManager.get_active
        if _get_active() == '' or _get_active() == self.name:
            return True
        else:
            return False


def create_skill():
    return SpotifySkill()
