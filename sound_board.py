import sys
import os
import json
import random

from typing import Union
from dataclasses import dataclass
from collections import defaultdict

import pygame

DEFAULT_CHANNELS = 8
DEFAULT_IGNORE_CASE = True

# Probably overkill
import logging
logger = logging.getLogger("[Sound Board]")

class SoundError(Exception): pass

@dataclass(frozen=True)
class Ambient:
    filename: str
    key: str = None
    autostart: bool = False
    loops: int = -1.0
    volume: float = 1.0
    fade_in: int = 0

@dataclass(frozen=True)
class Effect:
    filename: str
    channel: int
    key: str
    loops: int = 0
    retrigger: bool = False
    volume: float = 1.0
    fade_in: int = 0

class SoundBoard:
    def __init__(self, 
                 channels: int = 8,
                 ignore_case: bool = True,
                 logging_level: int = logging.CRITICAL):
        logging.basicConfig(level=logging_level)

        pygame.mixer.init()
        pygame.mixer.set_num_channels(channels)
        ch = pygame.mixer.get_num_channels()
        if ch < channels:
            raise SoundError(f"Tried to allocate {channels} channels but only got {ch}")
        self.channels = tuple([pygame.mixer.Channel(i) for i in range(channels)])
        self.ignore_case = ignore_case
        logging.info(f"Allocated {ch} sound channels")
        
        self._ambients = []
        self._effects = dict()
        self._keys = defaultdict(list)

        self.control_keys = dict()
        self.paused = False
        self.current_ambient = None

    @property
    def keys(self):
        return self._keys
    
    @property
    def ambients(self):
        return self._ambients
    
    @property
    def effects(self):
        return self._effects
    
    def add_effect(self, effect: Effect):
        if not (0 <= effect.channel < len(self.channels)):
            raise SoundError(f"Invalid channel {effect.channel} for {effect.filename}")
        if not (0.0 <= effect.volume <= 1.0):
            raise SoundError(f"Invalid volume ({effect.volume}) for {effect.filename!r}")
        if effect.fade_in < 0:
            raise SoundError(f"Invalid fade_in ({effect.fade_in} ms) for {effect.filename!r}")
        
        key = effect.key.lower() if self.ignore_case else effect.key
        if key in self.control_keys:
            raise SoundError(f"Control {key!r} already in use for {self.control_keys[key]}")
        sound = pygame.mixer.Sound(effect.filename)
        sound.set_volume(effect.volume)
        self._keys[key].append(effect)
        self._effects[effect] = sound
    
    def remove_effect(self, effect: Effect):
        if effect not in self._effect:
            raise SoundError(f"Cannot remove {effect.filename!r}. Effect not found.")
        del self._effects[effect]
        k = effect.key.lower if self.ignore_case else effect.key
        ix = self._keys[k].index(effect)
        self._keys[k].pop(ix)
    
    def add_ambient(self, ambient: Ambient):
        if not (0.0 <= ambient.volume <= 1.0):
            raise SoundError(f"Invalid volume ({ambient.volume}) for {ambient.filename!r}")
        if ambient.fade_in < 0:
            raise SoundError(f"Invalid fade_in ({ambient.fade_in} ms) for {ambient.filename!r}")
        if not os.access(ambient.filename, mode=os.R_OK):
            raise SoundError(f"File not found: {ambient.filename!r}")

        if ambient.key is not None:
            key = ambient.key.lower() if self.ignore_case else ambient.key
            if key in self.control_keys:
                raise SoundError(f"Control {key!r} already in use for {self.control_keys[key]}")
            # XXX: Check to make sure that only one ambient sound is
            #      assigned to each key.
            for snd in self._keys[key]:
                if isinstance(snd, Ambient):
                    raise SoundError(f"Error: Multiple ambient sounds assigned to {ambient.key!r}")
            self._keys[key].append(ambient)
        self._ambients.append(ambient)

    def remove_ambient(self, ambient: Ambient):
        if ambient not in self._ambients:
            raise SoundError(f"Cannot remove {ambient.filename!r}. Ambient not found.")
        ix = self._ambients.index(ambient)
        self._ambients.pop(ix)

        if ambient.key:
            k = ambient.key.lower if self.ignore_case else ambient.key
            ix = self._keys[k].index(ambient)
            self._keys[k].pop(ix)
    
    def play_ambient(self, ambient: Ambient):
        logger.info(f"Playing ambient sound: {ambient.filename}")
        pygame.mixer.music.load(ambient.filename)
        pygame.mixer.music.set_volume(ambient.volume)
        pygame.mixer.music.play(loops=ambient.loops, fade_ms=ambient.fade_in)
        self.current_ambient = ambient

    def play_effect(self, effect: Effect):
        sound = self._effects[effect]
        chan = self.channels[effect.channel]
        loops = effect.loops

        if chan.get_busy(): # Channel is currently playing
            playing = chan.get_sound()
            if playing == sound:
                if effect.retrigger:    # Restart the effect
                    logger.info(f"Restarting effect: {effect.filename}")
                    chan.play(sound, loops=loops, fade_ms=effect.fade_in)
                else:                   # Stop the effect
                    logger.info(f"Stopping effect: {effect.filename}")
                    chan.stop()
            else:   # Stop the old effect on this channel and start a new one
                logger.info(f"Playing new effect: {effect.filename}")
                chan.stop()
                chan.play(sound, loops=loops, fade_ms=effect.fade_in)
        else: # Start playing an effect
            logger.info(f"Playing effect: {effect.filename}")
            chan.play(sound, loops=loops, fade_ms=effect.fade_in)

    def start(self):
        self.start_ambient(True)
        
    def start_ambient(self, only_autoplay: bool=True):
        if only_autoplay:
            valid = [a for a in self._ambients if a.autostart]
        else:
            valid = self._ambients
        self.play_ambient(random.choice(valid))

    def stop(self):
        pygame.mixer.music.stop()
        self.current_ambient = None

        for ch in self.channels:
            ch.stop()
        logger.info("All sounds stopped")

    def volume(self, delta: float):
        logger.info(f"Changing volume by {delta:.2f}")
        
        if pygame.mixer.music.get_busy():   # Ambient is playing
            max_volume = self.current_ambient.volume
            target_volume = pygame.mixer.music.get_volume() + delta
            vol = max(0, min(target_volume, max_volume))
            pygame.mixer.music.set_volume(vol)
            # logger.info(f"Ambient sound volume: {vol:.2f}")

        for ix, ch in enumerate(self.channels):
            target_volume = ch.get_volume() + delta
            vol = max(0, min(target_volume, 1.0))
            ch.set_volume(vol)
            # logger.info(f"Channel {ix} volume: {vol:.2f}")

    def pause(self):
        if not self.paused:
            pygame.mixer.music.pause()
            for ch in self.channels:
                ch.pause()
            logger.info("All sounds paused")
        else:
            pygame.mixer.music.unpause()
            for ch in self.channels:
                ch.unpause()
            logger.info("All sounds resumed")
        self.paused = not self.paused

    def is_playing(self, snd: Union[Ambient, Effect]) -> bool:
        if isinstance(snd, Effect):
            ch = snd.channel
            if self.channels[ch].get_busy():
                return self.channels[ch].get_sound() == self._effects[snd]
            return False
        elif isinstance(snd, Ambient):
            if pygame.mixer.music.get_busy():
                return snd == self.current_ambient
            return False
        else:
            raise TypeError("Cannot check if {type(snd)} is playing.")
        
    def key_press(self, key: str) -> list:
        k = key.lower() if self.ignore_case else key
        if k in self.control_keys:
            action = self.control_keys[k]
            if action == 'stop_key':
                self.stop()
            elif action == 'pause_key':
                self.pause()
            elif action == 'volume_up':
                self.volume(0.1)
            elif action == 'volume_down':
                self.volume(-0.1)
            else:
                logger.critical(f"Unknown action: {action!r}")
            return [action]

        if k not in self._keys:
            return []
        
        playing = []
        for sound in self._keys[k]:
            if isinstance(sound, Ambient):
                self.play_ambient(sound)
                playing.append(sound)
            elif isinstance(sound, Effect):
                self.play_effect(sound)
                playing.append(sound)

        return playing
    
def load_json(config_filename: str, 
              logging_level: int = logging.CRITICAL) -> SoundBoard:
    with open(config_filename, 'r') as fp:
        cfg = json.load(fp)

        channels = int(cfg['player'].get('channels', DEFAULT_CHANNELS))
        ignore_case = bool(cfg['player'].get('ignore_case', DEFAULT_IGNORE_CASE))
        board = SoundBoard(channels, ignore_case, logging_level)

        for action in ('stop_key', 'pause_key', 'volume_up', 'volume_down'):
            if action in cfg['player']:
                key = cfg['player'][action].lower() if ignore_case else cfg['player'][action]
                if key in board.control_keys:
                    raise SoundError("Sound action {board.control_keys[key]!r} alreadys assigned to {key!r}")
                board.control_keys[key] = action                

        for music in cfg.get('ambients', []):
            if 'filename' not in music:
                raise SoundError("Config Error: Missing filename in ambient sounds.")
            ambient = Ambient(music['filename'],
                              music.get('key', None),
                              music.get('autostart', False),
                              music.get('loops', -1),
                              music.get('volume', 1.0),
                              music.get('fade_in', 0)
                             )
            board.add_ambient(ambient)

        for sound in cfg.get('effects', []):
            for required in ('filename', 'channel', 'key'):
                if required not in sound:
                    raise SoundError("Config Error: Missing {required} in effect sounds")

            effect = Effect(sound['filename'],
                            sound['channel'],
                            sound['key'],
                            sound.get('loops', 0),
                            sound.get('retrigger', False),
                            sound.get('volume', 1.0),
                            sound.get('fade_in', 0),
                           )
            board.add_effect(effect)
    
    return board

def test_board(json_file: str):
    from pprint import pprint

    print(f"Config file: {json_file!r}")
    board = load_json(json_file, logging.INFO)

    pygame.init()
    pygame.display.set_mode((640, 480), 0, 32)
    pygame.display.set_caption("Board Check")
    print("Press keys to trigger sounds")
    pprint(board.keys)
    pprint(board.control_keys)

    board.start()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break
            elif event.type == pygame.KEYDOWN:
                snd = board.key_press(event.unicode)
                if snd is None:
                    print(f"{event.unicode!r}: No sound assigned.")

    pygame.quit()

if __name__ == '__main__':
    test_board(sys.argv[1])

