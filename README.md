# YouTube2PeerTube

YouTube2PeerTube is a bot written in Python3 that mirrors YouTube channels,users or playlists to PeerTube channels.

This tool does not use YouTube APIs. Instead, it subscribes to youtube via RSS.

If you need to archive a YouTube channel with lots of existing videos, this tool is not for you. This tool starts mirroring channels from the time they are added to the config and will not mirror all historical videos that exist in a YouTube channel. A tool that provides this functionality is available https://github.com/Chocobozzz/PeerTube/blob/develop/support/doc/tools.md#peertube-import-videosjs

## Installation

To install, clone the repository to a directory on your machine. Then, navigate to that directory in a terminal and run:

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

This will create a virtual environment for the tool and install all dependencies required to run.

## Configuration

An example configuration file is found at example_config.toml. Copy this to config.toml and replace the fields with your information, and add channels as necessary.

The configuration file is found at config.toml. Each channel is capable of mirroring to a different PeerTube account and instance, and is capable of appending tags and description information on a per channel basis.

## Running the bot

To run the bot, simply run youtube2peertube.py. The bot will run indefinitely until stopped.

Any time the configuration is changed, the bot must be restarted.

## Thanks!

Thanks to the mps-youtube project https://github.com/mps-youtube for pafy, and thanks to LecygneNoir https://git.lecygnenoir.info/LecygneNoir for the prismedia project. Thank you Tom for TOML and as always, Guido and the Python team.

Thanks a lot to Mister-monster, https://github.com/mister-monster/YouTube2PeerTube
