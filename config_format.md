# Config Format

You should have a JSON config file that lists all of the sound files
and the sound board configuration.  See the example_config.json for
guidance

## Sections

There are three sections to the config file:

### Player

Configures the player. Keys assigned here cannot be used to trigger sounds.

```
"player": {"channels": 8,
           "ignore_case": true,
           "stop_key": "z",
           "pause_key": "x",
           "volume_up": "c",
           "volume_down": "v"
          }
```

* `chanels`: The (integer) number of channels to allocate at startup. [Default: 8]
* `ignore_case`: The case of the keyboard interrupt is ignored. [Default: true]
* `stop_key`: Stops all effects and ambients. [Default: None]
* `pause_key`: Pauses/unpauses all effects and ambients. [Default: None]
* `volume_up`: Increases volume by 0.1 [Default: None]
* `volume_down`: Decreases volume by 0.1 [Default: None]

### Ambient Sounds

Ambient sounds are longer background music.  They are run through the music
mixer not the sound mixer.  Only one can play at a time.  Can accomidate very 
large files.  At startup, one of the ambient sounds tagged with `autostart` is
queued. Multiple effects and one ambient may be assigned to a key.  Multiple
ambient sounds may not be assigned to one key.

```
"ambients": [{"filename": "background_music.mp3",
              "loops": -1,
              "volume": 0.5,
              "key": "2",
              "fade_in": 100
             },
             [Optionally More Music Files Here]
            ]
```

* `filename`: Path to the music file.
* `key`: Key press to play this file.
* `autostart`: At startup, we will select on file with autostart set to `true` to play. [Default: false]
* `loops`: Set to -1 to loop forever, 0 to play once, N to loop N times. [Default: -1]
* `volume`: Set in the range 0 (silent) to 1.0 (full volume).  Use to fine tune audio without remixing. [Default: 1.0]
* `fade_in`: Set to a positive (or zero) number of milliseconds to fade in the music.  Probably best to build this into the sound file but this gives you some options. [Default: 0]

### Effects

These are shorter sound effect that can be triggered either by keyboard input or 
by the main boat programme. There are N (Default: 8) channels and each channel can
only play one sound at a time.  Each sound must specify which channel it is played
on.  Multiple suonds can be assigned to the same key and they will all play
with the same keypress if they are on different channels.


```
"effects": [{"filename": "effect_1.mp3",
             "channel": 1,
             "key": "a",
             "retrigger": false,
             "volume": 1.0,
             "loops": 0,
             "fade_in": 100,
            },
            [Optionally More Sound Files Here]
           ]
```

* `filename`: Path to the music file.
* `channel`: Which channel group to play the sound on.  Must be in the range 0 - (Number of Channels - 1)
* `key`: Key press to play this file.
* `retrigger`: When `true`, if you play this sound while it is playing it will restart. If set to `false` triggering this sound again will stop playback. [Default: false]
* `volume`: Set in the range 0 (silent) to 1.0 (full volume).  Use to fine tune audio without remixing. [Default: 1.0]
* `loops`: Set to -1 to loop forever, 0 to play once, N to loop N times. [Default: 0]
* `fade_in`: Set to a positive (or zero) number of milliseconds to fade in the effect.  Probably best to build this into the sound file but this gives you some options. [Default: 0]

