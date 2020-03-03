#!/usr/bin/python3

import pafy
import feedparser as fp
from urllib.request import urlretrieve
import requests
import json
from time import sleep
from os import mkdir, path
from shutil import rmtree
import mimetypes
from requests_toolbelt.multipart.encoder import MultipartEncoder
import utils


# Init du logger 

import logging
from logging.handlers import RotatingFileHandler

# création de l'objet logger qui va nous servir à écrire dans les logs
logger = logging.getLogger()
# on met le niveau du logger à DEBUG, comme ça il écrit tout
logger.setLevel(logging.DEBUG)

# création d'un formateur qui va ajouter le temps, le niveau
# de chaque message quand on écrira un message dans le log
formatter = logging.Formatter('%(asctime)s :: %(levelname)s :: %(message)s')
# création d'un handler qui va rediriger une écriture du log vers
# un fichier en mode 'append', avec 1 backup et une taille max de 1Mo
file_handler = RotatingFileHandler('activity.log', 'a', 1000000, 1)
# on lui met le niveau sur DEBUG, on lui dit qu'il doit utiliser le formateur
# créé précédement et on ajoute ce handler au logger

file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# création d'un second handler qui va rediriger chaque écriture de log
# sur la console
stream_formatter = logging.Formatter('%(asctime)s :: %(levelname)s :: %(message)s')
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.DEBUG)
stream_handler.setFormatter(stream_formatter)
logger.addHandler(stream_handler)


def get_video_data(channel_id,peertube_channel,peertube_instance_url):
    yt_rss_url = "https://www.youtube.com/feeds/videos.xml?user=" + channel_id
    feed = fp.parse(yt_rss_url)
    channel_lang = feed["feed"]["title_detail"]["language"]
    entries = feed["entries"]
    # clear any existing queue before start
    queue = []
    
    peertube_videos_url = peertube_instance_url+"/api/v1/video-channels/"+peertube_channel+"/videos"
    logger.info("Fetching peertube videos from channel %s ...",peertube_channel)
    peertube_videos = requests.get(peertube_videos_url)

    if handle_peertube_result(peertube_videos):
        for pos, i in enumerate(reversed(entries)):
            same_videos = [True for peertube_video in peertube_videos.json()['data'] if i['title'] == peertube_video['name'] ]
            if not same_videos:
                logger.debug(" -" + i['title'] + " add to queue")
                queue.append(i)
    else:
        logger.warning('Peertube api return %s code', peertube_videos.status_code)
    
    if not queue:
        logger.info("all videos already exist in channel %s",peertube_channel)
    # read contents of channels_timestamps.csv, create list object of contents
    return queue, channel_lang

def save_metadata(queue_item, dl_dir, channel_conf):
    dl_dir = dl_dir + channel_conf["name"]
    link = queue_item["link"]
    title = queue_item["title"]
    description = queue_item["summary"]
    author = queue_item["author"]
    published = queue_item["published"]
    metadata_file = dl_dir + "/" + queue_item["yt_videoid"] + ".txt"
    metadata = open(metadata_file, "w+")
    # save relevant metadata as semicolon separated easy to read values to text file
    metadata.write('title: "' + title + '";\n\nlink: "' + link + '";\n\nauthor: "' + author + '";\n\npublished: "' +
                   published + '";\n\ndescription: "' + description + '"\n\n;')
    # save raw metadata JSON string
    metadata.write(str(queue_item))
    metadata.close()

def get_pt_auth(channel_conf):
    # get variables from channel_conf
    pt_api = channel_conf["peertube_instance"] + "/api/v1"
    pt_uname = channel_conf["peertube_username"]
    pt_passwd = channel_conf["peertube_password"]
    # get client ID and secret from peertube instance
    id_secret = json.loads(str(requests.get(pt_api + "/oauth-clients/local").content).split("'")[1])
    client_id = id_secret["client_id"]
    client_secret = id_secret["client_secret"]
    # construct JSON for post request to get access token
    auth_json = {'client_id': client_id,
                 'client_secret': client_secret,
                 'grant_type': 'password',
                 'response_type': 'code',
                 'username': pt_uname,
                 'password': pt_passwd
                 }
    # get access token
    auth_result = json.loads(str(requests.post(pt_api + "/users/token", data=auth_json).content).split("'")[1])
    access_token = auth_result["access_token"]
    return access_token

def get_pt_channel_id(channel_conf):
    pt_api = channel_conf["peertube_instance"] + "/api/v1"
    post_url = pt_api + "/video-channels/" + channel_conf["peertube_channel"] + "/"
    returned_json = json.loads(requests.get(post_url).content)
    channel_id = returned_json["id"]
    return channel_id

def get_file(file_path):
    mimetypes.init()
    return (path.basename(file_path), open(path.abspath(file_path), 'rb'),
            mimetypes.types_map[path.splitext(file_path)[1]])


def handle_peertube_result(request_result):
    #sleep(1000)
    if request_result.status_code < 300:
        return True
    else:
        logger.warning("request error: %s",request_result.status_code)
        return False
    
def pt_http_import(channel_conf, queue_item, access_token,yt_lang):
    pt_api = channel_conf["peertube_instance"] + "/api/v1"
    yt_video_url = queue_item["link"]
    # TODO: use the alternate link if video not found error occurs
    alternate_link = queue_item["links"][0]["href"]
    description = channel_conf["description_prefix"] + "\n\n" + queue_item["summary"] + "\n\n" + channel_conf["description_suffix"]
    channel_id = str(get_pt_channel_id(channel_conf))
    language = utils.set_pt_lang(yt_lang, channel_conf["default_lang"])
    category = utils.set_pt_category(channel_conf["pt_channel_category"])
    
    fields = {
        "name":queue_item["title"],
        "licence":"1",
        "description":description,
        "nsfw":channel_conf["nsfw"],
        "channelId":channel_id,
        "originallyPublishedAt":queue_item["published"],
        "category":category,
        "privacy":str(channel_conf["pt_privacy"]),
        "language":language,
        "commentsEnabled":channel_conf["comments_enabled"],
        "targetUrl":yt_video_url,
        "waitTranscoding":'false'
    }
    
    if channel_conf["pt_tags"]:
        fields["tags"] = channel_conf["pt_tags"]
    else:
        logger.warning("you have no tags in your configuration file for this channel")

    headers = {
        'Content-Type': 'application/json',
        'Authorization': "Bearer " + access_token
    }
    
    return handle_peertube_result(requests.post(pt_api + "/videos/imports", data=json.dumps(fields), headers=headers))
        

def run_steps(conf):
    channel = conf["channel"]
    global_conf = conf["global"]
    # run loop for every channel in the configuration file
    for c in channel:
        channel_conf = channel[c]
        queue,yt_lang = get_video_data(channel_conf["channel_id"],channel_conf["peertube_channel"],channel_conf["peertube_instance"])
        if len(queue) > 0:
            access_token = get_pt_auth(channel_conf)
            for queue_item in queue:
                logger.info("mirroring " + queue_item["link"] + " to Peertube using HTTP import...")
                pt_result = pt_http_import(channel_conf, queue_item, access_token, yt_lang)

def run(run_once=True):
    #TODO: turn this into a daemon
    conf = utils.read_conf("config.toml")
    if run_once:
        run_steps(conf)
    else:
        while True:
            poll_frequency = int(conf["global"]["poll_frequency"]) * 60
            run_steps(conf)
            print("all jobs done... sleeping")
            sleep(poll_frequency)

if __name__ == "__main__":
    run(run_once=False)
