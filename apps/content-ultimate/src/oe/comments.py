"""Lấy comment top qua YouTube Data API — MODULE DUY NHẤT chạm API này. Xoay nhiều key.

commentThreads (1 unit/call, 100 comment/call):
  GET https://www.googleapis.com/youtube/v3/commentThreads
      ?part=snippet&videoId=<id>&maxResults=100&order=relevance&textFormat=plainText&key=<k>
  items[].snippet.topLevelComment.snippet: {textDisplay, likeCount, publishedAt}
  items[].snippet.totalReplyCount · d.nextPageToken để phân trang.
  403 quotaExceeded / commentsDisabled → xoay key / bỏ qua video.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

API = "https://www.googleapis.com/youtube/v3/commentThreads"


class CommentsDisabled(Exception):
    pass


class AllKeysExhausted(Exception):
    pass


@dataclass(frozen=True)
class Comment:
    text: str
    likes: int
    replies: int


class CommentClient:
    """Xoay danh sách key: hết quota key này thì sang key kế; hết sạch thì raise."""

    def __init__(self, keys: list[str]):
        self.keys = [k for k in keys if k]
        self.i = 0

    def _get(self, params: dict) -> dict:
        last = None
        while self.i < len(self.keys):
            q = urllib.parse.urlencode(dict(params, key=self.keys[self.i]))
            try:
                with urllib.request.urlopen(f"{API}?{q}", timeout=30) as r:
                    return json.loads(r.read())
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "ignore")
                if e.code == 403 and "commentsDisabled" in body:
                    raise CommentsDisabled()
                if e.code in (403, 429) and ("quota" in body.lower() or "rateLimit" in body):
                    self.i += 1                       # xoay sang key kế
                    last = body
                    continue
                raise
        raise AllKeysExhausted(last or "hết key")

    def fetch(self, video_id: str, *, max_comments: int = 300) -> list[Comment]:
        out: list[Comment] = []
        token = None
        while len(out) < max_comments:
            params = {"part": "snippet", "videoId": video_id, "maxResults": 100,
                      "order": "relevance", "textFormat": "plainText"}
            if token:
                params["pageToken"] = token
            d = self._get(params)
            for it in d.get("items", []):
                s = it["snippet"]["topLevelComment"]["snippet"]
                out.append(Comment(s.get("textDisplay", ""), int(s.get("likeCount", 0)),
                                   int(it["snippet"].get("totalReplyCount", 0))))
            token = d.get("nextPageToken")
            if not token:
                break
        return out[:max_comments]
