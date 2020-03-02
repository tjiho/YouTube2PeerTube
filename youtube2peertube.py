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

def get_video_data(channel_id,peertube_channel):
    yt_rss_url = "https://www.youtube.com/feeds/videos.xml?user=" + channel_id
    feed = fp.parse(yt_rss_url)
    channel_lang = feed["feed"]["title_detail"]["language"]
    entries = feed["entries"]
    # clear any existing queue before start
    queue = []
    
    peertube_videos_url = "https://tube.fede.re"+"/api/v1/video-channels/"+peertube_channel+"/videos"

    peertube_videos = requests.get(peertube_videos_url)
    if peertube_videos.status_code == 200:
        for pos, i in enumerate(reversed(entries)):
            same_videos = [True for peertube_video in peertube_videos.json()['data'] if i['title'] == peertube_video['name'] ]
            if not same_videos:
                print(i['title'] + " add to queue")
                queue.append(i)
    # read contents of channels_timestamps.csv, create list object of contents
    return queue, channel_lang

def download_yt_video(queue_item, dl_dir, channel_conf):
    url = queue_item["link"]
    dl_dir = dl_dir + channel_conf["name"]
    try:
        video = pafy.new(url)
        streams = video.streams
        #for s in streams:
            #print(s.resolution, s.extension, s.get_filesize, s.url)
        best = video.getbest(preftype=channel_conf["preferred_extension"])
        filepath = dl_dir + "/"+ queue_item["yt_videoid"] + "." + channel_conf["preferred_extension"]
        #TODO: implement resolution logic from config, currently downloading best resolution
        best.download(filepath=filepath, quiet=False)

    except:
        pass
        # TODO: check YT alternate URL for video availability
        # TODO: print and log exceptions

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

def save_thumbnail(queue_item, dl_dir, channel_conf):
    dl_dir = dl_dir + channel_conf["name"]
    thumb = str(queue_item["media_thumbnail"][0]["url"])
    extension = thumb.split(".")[-1]
    thumb_file = dl_dir + "/" + queue_item["yt_videoid"] + "." + extension
    # download the thumbnail
    urlretrieve(thumb, thumb_file)
    return extension

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
        print(request_result)
        return False
    
def pt_http_import(channel_conf, queue_item, access_token,yt_lang):
    # Adapted from Prismedia https://git.lecygnenoir.info/LecygneNoir/prismedia
    pt_api = channel_conf["peertube_instance"] + "/api/v1"
    yt_video_url = queue_item["link"]
    # TODO: use the alternate link if video not found error occurs
    alternate_link = queue_item["links"][0]["href"]
    description = channel_conf["description_prefix"] + "\n\n" + queue_item["summary"] + "\n\n" + channel_conf["description_suffix"]
    channel_id = str(get_pt_channel_id(channel_conf))
    language = utils.set_pt_lang(yt_lang, channel_conf["default_lang"])
    category = utils.set_pt_category(channel_conf["pt_channel_category"])
    # We need to transform fields into tuple to deal with tags as
    # MultipartEncoder does not support list refer
    # https://github.com/requests/toolbelt/issues/190 and
    # https://github.com/requests/toolbelt/issues/205
    fields = {
            "name":queue_item["title"],
            "licence":"1",
        "description":description,
        "nsfw":channel_conf["nsfw"],
        "channelId":channel_id,
        "originallyPublishedAt":queue_item["published"],
        "category":category,
        "privacy":"1",
        "language":language,
        "commentsEnabled":channel_conf["comments_enabled"],
        "targetUrl":yt_video_url,
        #"thumbnailfile":get_file(thumb_file),
        #"previewfile":get_file(thumb_file),
        "waitTranscoding":'false'
    }
    if channel_conf["pt_tags"] != "":
        fields["tags"] = channel_conf["pt_tags"]
    else:
        print("you have no tags in your configuration file for this channel")

    headers = {
        'Content-Type': 'application/json',
        'Authorization': "Bearer " + access_token
    }
    
    return handle_peertube_result(requests.post(pt_api + "/videos/imports", data=json.dumps(fields), headers=headers))
        

def log_upload_error(yt_url,channel_conf):
    error_file = open("video_errors.csv", "a")
    error_file.write(channel_conf['name']+","+yt_url+"\n")
    error_file.close()
    print("error !")

def run_steps(conf):
    # TODO: logging
    channel = conf["channel"]
    # run loop for every channel in the configuration file
    global_conf = conf["global"]
    channel_counter = 0
    for c in channel:
        print("\n")
        channel_id = channel[c]["channel_id"]
        channel_conf = channel[str(channel_counter)]
        video_data = get_video_data(channel_id,channel[c]["peertube_channel"])
        queue = video_data[0]
        yt_lang = video_data[1]
        if len(queue) > 0:
            # download videos, metadata and thumbnails from youtube
            access_token = get_pt_auth(channel_conf)
            # upload videos, metadata and thumbnails to peertube
            for queue_item in queue:
                print("mirroring " + queue_item["link"] + " to Peertube using HTTP import...")
                pt_result = pt_http_import(channel_conf, queue_item, access_token, yt_lang)
                print("waiting...")
                sleep(3)
                if pt_result:
                    print("done !")
                else:
                    log_upload_error(queue_item["link"],channel_conf)

        channel_counter += 1

def run(run_once=True):
    #TODO: turn this into a daemon
    conf = utils.read_conf("config.toml")
    if run_once:
        run_steps(conf)
    else:
        while True:
            poll_frequency = int(conf["global"]["poll_frequency"]) * 60
            run_steps(conf)
            sleep(poll_frequency)

if __name__ == "__main__":
    run(run_once=False)
