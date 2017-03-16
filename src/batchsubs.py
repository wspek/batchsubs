"""
 Created by waldo on 3/15/17
"""

import sys
import argparse
import base64
import zlib
import util
from os import listdir
from pythonopensubtitles.opensubtitles import OpenSubtitles
from pythonopensubtitles.utils import File

__author__ = "waldo"
__project__ = "batchsubs"

LOG_LOCATION = "../logs/{0}.log".format("batchsubs")


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
            "help": "opensubtitles.org username",
            "metavar": "USERNAME"
        },
        {
            "name": "-p",
            "required": True,
            "type": str,
            "default": None,
            "help": "opensubtitles.org password",
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
            "help": "file extension for which to download subtitles",
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
        credentials = {
            "username": self.vargs['u'],
            "password": self.vargs['p'],
        }

        arguments = {
            "folder": self.vargs['i'],
            "video_format": self.vargs['f'],
            "language": self.vargs['l'],
            "choice": self.vargs['c'],
        }

        batchsubs = BatchSubs()
        batchsubs.login(**credentials)
        batchsubs.download_subs_in_folder(**arguments)
        batchsubs.logout()


class BatchSubs(object):
    def __init__(self):
        self.logger = util.get_logger(__name__, LOG_LOCATION)
        self.choice = 1
        self.token = ""
        self.opensubs = OpenSubtitlesExtended()

    def login(self, username, password):
        self.logger.info("Logging into OpenSubtitles.org and requesting token.")

        self.token = self.opensubs.login(username, password)

        self.logger.debug("Token acquired.")

    def logout(self):
        self.logger.info("Logging out.")

        self.opensubs.logout()

    def download_subs_in_folder(self, folder, video_format, language, choice):
        self.choice = choice

        self.logger.debug("Creating list of '{0}' files in folder '{1}'.".format(video_format, folder))
        file_list = [file_name for file_name in listdir(folder) if file_name.split('.')[-1] == video_format]

        download_list = {}
        for file_name in file_list:
            video_file = File("/".join((folder, file_name)))
            file_hash = video_file.get_hash()
            file_size = video_file.size

            self.logger.info("Processing file '{0}' - hash: {1} - size: {2}".format(file_name, file_hash, file_size))
            self.logger.debug("Creating list of corresponding subtitles.")

            subtitles = self.opensubs.search_subtitles(
                [{'sublanguageid': language, 'moviehash': file_hash, 'moviebytesize': file_size}])

            self.logger.debug("Cleaning up subtitles to contain only interesting data.")

            subtitles_clean = self._clean_up(subtitles)

            self.logger.debug("Getting {0}st choice subtitles.".format(choice))

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

        self.logger.info("Downloading and saving all #{0} choice subtitles.".format(choice))

        self._download_subtitles(download_list)

        self.logger.info("Subtitles saved in folder '{0}'.".format(folder))

    def _download_subtitles(self, download_list):
        file_ids = download_list.keys()
        subtitles = self.opensubs.download_subtitles(file_ids)

        for subtitle in subtitles:
            subtitle_id = subtitle["idsubtitlefile"]
            subtitle_decompressed = self._decode_unzip(subtitle["data"])

            file_name = download_list[subtitle_id]
            with open(file_name, 'w') as sub_file:
                sub_file.write(subtitle_decompressed)

    def _get_choice(self, subtitle_list, choice_nr):
        # Sort the dictionary according to number of downloads (descending)
        sorted_list = sorted(subtitle_list, key=lambda k: int(k['SubDownloadsCnt']), reverse=True)

        # Get the requested choice, or the last element if out of bounds
        try:
            sub_of_choice = sorted_list[choice_nr - 1]
        except IndexError:
            self.choice = len(sorted_list)
            sub_of_choice = sorted_list[-1]

        return sub_of_choice

    @staticmethod
    def _clean_up(subtitles):
        fields_of_interest = ["SubComments", "SubFileName", "SubBad", "SubLanguageID", "SeriesEpisode",
                              "SubEncoding", "SubDownloadsCnt", "SeriesSeason", "IDSubtitle", "IDSubtitleFile"]

        clean_list = []
        for subtitle in subtitles:
            clean_elem = {field: subtitle.get(field, None) for field in fields_of_interest}
            clean_list.append(clean_elem)

        return clean_list

    @staticmethod
    def _decode_unzip(subtitle_base64_zipped):
        subtitle_gzip = base64.b64decode(subtitle_base64_zipped)
        return zlib.decompress(subtitle_gzip, 16 + zlib.MAX_WBITS)


class OpenSubtitlesExtended(OpenSubtitles):
    def __init__(self):
        self.data = None

    def _get_from_data(self, key):
        return self.data.get(key)

    def get_languages(self):
        self.data = self.xmlrpc.GetSubLanguages()
        return self._get_from_data('data')

    def download_subtitles(self, params):
        self.data = self.xmlrpc.DownloadSubtitles(self.token, params)
        return self._get_from_data('data')


def main():
    BatchSubsTool().run()


if __name__ == '__main__':
    main()
