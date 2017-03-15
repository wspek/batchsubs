"""
 Created by waldo on 3/15/17
"""

__author__ = "waldo"
__project__ = "batchsubs"

import sys
import argparse
import logging
import base64
import zlib
from os import listdir
from pythonopensubtitles.opensubtitles import OpenSubtitles
from pythonopensubtitles.utils import File


class CommandLineTool(object):
    # overload in the actual subclass
    #
    AP_PROGRAM = sys.argv[0]
    AP_DESCRIPTION = u"Generic Command Line Tool"
    AP_ARGUMENTS = [
        # required args
        # {"name": "foo", "nargs": 1, "type": str, "default": "baz", "help": "Foo help"},
        #
        # optional args
        # {"name": "--bar", "nargs": "?", "type": str,, "default": "foofoofoo", "help": "Bar help"},
        # {"name": "--quiet", "action": "store_true", "help": "Do not output to stdout"},
    ]

    # noinspection PyArgumentList,PyTypeChecker,PyTypeChecker
    def __init__(self):
        self.parser = argparse.ArgumentParser(
            prog=self.AP_PROGRAM,
            description=self.AP_DESCRIPTION,
            formatter_class=lambda prog: argparse.HelpFormatter(prog, width=110, max_help_position=64)
        )
        self.vargs = None

        # Create a dictionary of mutually exclusive groups
        groups = dict()
        for arg in self.AP_ARGUMENTS:
            # Return the mutually exclusive group or 'None' if not present.
            group = arg.pop("group", None)
            if group is not None:
                # If the group name has not been added to the groups dict() yet, add it as a key, with an empty list
                # as value. Otherwise, append the arguments to the already existing groups entry.
                groups.setdefault(group, []).append(arg)
            else:
                self.parser.add_argument(arg.pop("name"), **arg)

        # If there are mutually exclusive groups to be made, we go into this loop
        for group_name, arguments in groups.iteritems():
            group = self.parser.add_mutually_exclusive_group()
            for arg in arguments:
                name = arg.pop("name")
                group.add_argument(name, **arg)

    def run(self):
        self.vargs = vars(self.parser.parse_args())
        self.actual_command()

    # overload this in your actual subclass
    def actual_command(self):
        self.print_stdout(u"This script does nothing. Invoke another .py")


class BatchSubsTool(CommandLineTool):
    AP_PROGRAM = u"Batch subtitle downloader"
    AP_DESCRIPTION = u"Download subtitles in batch from OpenSubtitles.org."
    AP_ARGUMENTS = [
        {
            "name": "-u",
            "required": True,
            "type": str,
            "default": None,
            "help": "username of the OpenSubtitles.org account used to retrieve.",
            "metavar": "USERNAME"
        },
        {
            "name": "-p",
            "required": True,
            "type": str,
            "default": None,
            "help": "password of the  OpenSubtitles.org account used to retrieve.",
            "metavar": "PASSWORD"
        },
        {
            "name": "-i",
            "required": True,
            "type": str,
            "default": None,
            "help": "input folder",
            "metavar": "FOLDER"
        },
        {
            "name": "-f",
            "required": True,
            "type": str,
            "default": None,
            "help": "format of files for which to download subtitles",
            "choices": ["mkv", "avi"]
        },
        {
            "name": "-l",
            "required": True,
            "type": str,
            "default": None,
            "help": "subtitle language",
            "choices": ["eng", "spa"]
        },
        {
            "name": "-c",
            "nargs": '?',
            "type": int,
            "default": 1,
            "help": "if multiple choice are available, choose another than the first choice",
            "metavar": "NUMBER"
        },
    ]

    def actual_command(self):
        arguments = {
            "username": self.vargs['u'],
            "password": self.vargs['p'],
            "folder": self.vargs['i'],
            "video_format": self.vargs['f'],
            "language": self.vargs['l'],
            "choice": self.vargs['c'],
        }

        BatchSubs().download_subs_in_folder(**arguments)


class BatchSubs(object):
    def __init__(self):
        self.opensubs = OpenSubtitlesExtended()
        self.choice = 1

    def download_subs_in_folder(self, username, password, folder, video_format, language, choice):
        self.choice = choice

        # Login to OpenSubtitles.org and obtain a session token
        token = self.opensubs.login(username, password)

        # Make a list of files of specified 'video_format' that are contained in 'folder'
        file_list = [file_name for file_name in listdir(folder) if file_name.split('.')[-1] == video_format]

        # For each file in the list download the subtitle file
        download_list = {}
        for file_name in file_list:
            # File data necessary for download
            video_file = File("/".join((folder, file_name)))
            hash = video_file.get_hash()
            size = video_file.size

            # Get a list of subtitles and clean the list up to contain interesting data only
            subtitles = self.opensubs.search_subtitles(
                [{'sublanguageid': language, 'moviehash': hash, 'moviebytesize': size}])
            subtitles_clean = self._clean_up(subtitles)

            # Download the subtitles of our choice
            subtitle = self._get_choice(subtitles_clean, self.choice)
            save_path = u"{0}/S{1}E{2}_{3}_{4}_{5}_{6}_ID-{7}.srt".format(folder,
                                                                          subtitle["SeriesSeason"],
                                                                          subtitle["SeriesEpisode"],
                                                                          self.choice,
                                                                          subtitle["SubLanguageID"],
                                                                          subtitle["SubFileName"],
                                                                          subtitle["SubEncoding"],
                                                                          subtitle["IDSubtitleFile"])
            download_list[subtitle["IDSubtitleFile"]] = save_path

        self._download_subtitles(download_list)

    def _download_subtitles(self, download_list):
        id_list = download_list.keys()
        subtitle_list = self.opensubs.download_subtitles(id_list)

        for subtitle in subtitle_list:
            subtitle_id = subtitle["idsubtitlefile"]
            subtitle_decompressed = self._decode_unzip(subtitle["data"])

            file_name = download_list[subtitle_id]
            with open(file_name, 'w') as sub_file:
                sub_file.write(subtitle_decompressed)

    def _clean_up(self, subtitle_list):
        interesting_data = ["SubComments", "SubFileName", "SubBad", "SubLanguageID", "SeriesEpisode",
                            "SubEncoding", "SubDownloadsCnt", "SeriesSeason", "IDSubtitle", "IDSubtitleFile"]
        subtitle_list_clean = []

        for elem in subtitle_list:
            clean_elem = {k: elem.get(k, None) for k in interesting_data}
            subtitle_list_clean.append(clean_elem)

        return subtitle_list_clean

    def _get_choice(self, subtitle_list, number):
        # Sort the dictionary according to number of downloads (descending)
        newlist = sorted(subtitle_list, key=lambda k: int(k['SubDownloadsCnt']), reverse=True)

        # Get the requested choice, or the last element if out of bounds
        try:
            sub_choice = newlist[number - 1]
        except IndexError:
            self.choice = len(newlist)
            sub_choice = newlist[-1]

        return sub_choice

    def _decode_unzip(self, subtitle_base64_zipped):
        subtitle_gzip = base64.b64decode(subtitle_base64_zipped)
        return zlib.decompress(subtitle_gzip, 16 + zlib.MAX_WBITS)


class OpenSubtitlesExtended(OpenSubtitles):
    def _get_from_data(self, key):
        return self.data.get(key)

    def get_languages(self):
        self.data = self.xmlrpc.GetSubLanguages()
        return self._get_from_data('data')

    def download_subtitles(self, params):
        self.data = self.xmlrpc.DownloadSubtitles(self.token, params)
        return self._get_from_data('data')


def test():
    username = "batchsubs"
    password = "subsbatch"

    name = "Breaking Bad"
    path = "/media/waldo/DATA-SHARE/Downloads/Breaking Bad Season 2 Complete 720p.BRrip.Sujaidr/"
    video = "Breaking Bad s02ep1 720p brrip.sujaidr.mkv"
    subtitle = video[:-4] + ".srt"

    # Login
    ose = OpenSubtitlesExtended()
    token = ose.login(username, password)

    f = File("".join((path, video)))
    hash = f.get_hash()
    size = f.size

    data = ose.get_languages()

    # data = ose.search_subtitles([{'sublanguageid': 'all', 'moviehash': hash}])
    data = ose.search_subtitles([{'sublanguageid': 'spa', 'moviehash': hash, 'moviebytesize': size}])

    ID = data[0]['IDSubtitleFile']
    subtitle = ose.download_subtitles([ID])
    pass

    ose.logout()


def main():
    BatchSubsTool().run()


if __name__ == '__main__':
    main()
