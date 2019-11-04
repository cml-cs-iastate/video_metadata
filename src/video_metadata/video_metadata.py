from googleapiclient.discovery import build
import googleapiclient
from typing import Union, Optional, List
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"


class VideoMetadata:
    """Parses YouTube data api v3 video info
    Must check self.available when iterating for valid results
    """

    _CATEGORY_ID_TO_NAME = {"1": "Film & Animation",
                            "2": "Autos & Vehicles",
                            "10": "Music",
                            "15": "Pets & Animals",
                            "17": "Sports",
                            "18": "ShortMovies",
                            "19": "Travel & Events",
                            "20": "Gaming",
                            "21": "Videoblogging",
                            "22": "People & Blogs",
                            "23": "Comedy",
                            "24": "Entertainment",
                            "25": "News & Politics",
                            "26": "Howto & Style",
                            "27": "Education",
                            "28": "Science & Technology",
                            "29": "Nonprofits & Activism",
                            "30": "Movies",
                            "31": "Anime/Animation",
                            "32": "Action/Adventure",
                            "33": "Classics",
                            "34": "Comedy",
                            "35": "Documentary",
                            "36": "Drama",
                            "37": "Family",
                            "38": "Foreign",
                            "39": "Horror",
                            "40": "Sci-Fi/Fantasy",
                            "41": "Thriller",
                            "42": "Shorts",
                            "43": "Shows",
                            "44": "Trailers",
                            }

    def __init__(self,
                 video_id: Union[str, list] = '',
                 dev_key: str = '',
                 json: Optional[dict] = None,
                 client: Optional[googleapiclient.discovery.Resource] = None):
        """Ids and GCP key to use.
        :param video_id is an iterable collection of YouTube ids.
        :param dev_key: Google Cloud Platform dev key.
        :param client: Existing Google API client instance
        :type dev_key: str
        :type video_id: str, list
        :type client: Optional[googleapiclient.discovery.Resource]
        :raises: ValueError
        """
        # The index of the next video, unless current video is the last.
        self._index_next_video = 0

        # The youtube data api client
        if client:
            self.client = client
        elif dev_key:
            self.client = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=dev_key)
        else:
            raise ValueError("`video_id` and `dev_key` must be specified together")

        # Current video metadata
        self._current_metadata = None

        if video_id:
            self._get_video_metadata(video_id)
        else:
            self._multi_metadata = []

        if json:
            # Removes a double list when slicing results
            # The `items` value holds a list of video metadata results.
            # The index of that list tells the current result..
            self._multi_metadata = [x for x in json["items"]]

    def available(self) -> bool:
        """Did the API return a result that is useful?"""
        if self._current_video():
            return True
        else:
            return False

    def __len__(self):
        """Number of videos with metadata"""
        return len(self._multi_metadata)

    def __iter__(self):
        # Resetting the index allows for reiteration of the dataset
        self._index_next_video = 0
        return self

    def __next__(self):

        # The `current_metadata` variable will only update if there are more videos
        # Using the incremented index leads to Off by One errors (IndexErrors)
        try:
            self._current_metadata = self._multi_metadata[self._index_next_video]
        except IndexError:
            raise StopIteration
        self._index_next_video += 1

        # self is returned as it contains `_current_metadata`.
        # Returning `_current_metadata` would not allow for instance methods to operate on it.
        return self

    def __getitem__(self, item):
        """A new instance is made containing only the results sliced
        `items` is added back to have the same appearance as an actual api response"""
        return VideoMetadata(json={"items": self._multi_metadata[item]})

    @property
    def id(self) -> str:
        return self._current_video()["id"]

    @staticmethod
    def _convert_list_to_comma_string(ids):
        """Converts a list of video ids to format that the youtube api needs
        Comma separated video ids.
        """
        if isinstance(ids, str):
            return ids
        return ','.join(ids)

    def _get_video_metadata(self, yt_id: Union[List[str], str]):
        result = self.client.videos().list(part="snippet,contentDetails,statistics",
                                           fields="items(id, snippet(categoryId,channelId,channelTitle,defaultAudioLanguage,defaultLanguage,description,liveBroadcastContent,publishedAt,tags,title))",
                                           id=self._convert_list_to_comma_string(yt_id)).execute()["items"]
        self._multi_metadata = _mark_unavailable_videos(yt_id, result)
        self._current_metadata = self._multi_metadata[0]

    def _current_video(self) -> dict:
        return self._current_metadata

    @property
    def category_id(self) -> str:
        """Returns the numeric category of the video
        Returns an empty string if no category id is present"""
        snippet = self._current_video().get("snippet")
        if snippet is None:
            return ""
        cid = snippet.get("categoryId")
        if cid is None:
            return ""
        return cid

    @property
    def category_name(self) -> str:
        return self._CATEGORY_ID_TO_NAME[self.category_id]

    @property
    def channel_id(self) -> str:
        try:
            return self._current_video()["snippet"]["channelId"]
        except KeyError:
            return ""

    @property
    def channel_title(self) -> str:
        try:
            return self._current_video()["snippet"]["channelTitle"]
        except KeyError:
            return ""

    @property
    def title(self) -> str:
        return self._current_video()["snippet"]["title"]

    @property
    def keywords(self) -> list:
        """Returns a list of keywords attached to the video
        If there are no keywords an empty list is returned."""
        try:
            return self._current_video()["snippet"]["tags"]
        except KeyError:
            return []

    @property
    def description(self) -> str:
        """Description provided for video"""
        return self._current_video()["snippet"]["description"]

    @property
    def time_published(self) -> str:
        return self._current_video()["snippet"]["publishedAt"]


def _mark_unavailable_videos(vids_requested: List, vids_result: List) -> List:
    """Fills requests with unavailable video ids with None"""

    # Control advancement of yt results because API gives no indication of which videos are missing
    vids_request_iter = iter(vids_requested)
    some_info = []

    # No results matched for any videos requested
    no_vid_results = len(vids_result) == 0
    if no_vid_results:
        # Fill with empty results
        return [None] * len(vids_requested)

    # Advance through requests to match up with the available videos returned
    for vid_result in vids_result:
        matches = False
        while not matches:
            # Get next requested yt id
            request_yt_id = next(vids_request_iter)
            response_yt_id = vid_result["id"]
            if request_yt_id == response_yt_id:
                some_info.append(vid_result)
                # Found the matching response, move to next video response result
                matches = True
            else:
                # Video not available, Mark result as so
                some_info.append(None)

    # Any remaining requests had no responsive results
    for _ in vids_request_iter:
        some_info.append(None)

    return some_info
