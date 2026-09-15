import os
import time
from urllib.parse import quote

import requests
from dotenv import load_dotenv

from .rate_limiter import RateLimiter


class RiotClient:
    def __init__(self, region="europe", max_calls=100, period_seconds=120):
        load_dotenv()
        api_key = os.environ["RIOT_API_KEY"]

        self.headers = {"X-Riot-Token": api_key}
        self.region = region
        self.limiter = RateLimiter(max_calls=max_calls, period_seconds=period_seconds)

    def _get(self, url, params=None, max_retries=3):
        for attempt in range(max_retries):
            self.limiter.wait_if_needed()
            response = requests.get(url, headers=self.headers, params=params)
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 1))
                time.sleep(retry_after)
                continue
            return response
        raise RuntimeError("Trop de tentatives après rate limiting répété")

    def get_puuid(self, game_name, tag_line):
        url = (
            f"https://{self.region}.api.riotgames.com/riot/account/v1/accounts/"
            f"by-riot-id/{quote(game_name)}/{quote(tag_line)}"
        )
        response = self._get(url)
        response.raise_for_status()
        return response.json()["puuid"]

    def get_match_ids(self, puuid, count=10):
        url = f"https://{self.region}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
        response = self._get(url, params={"start": 0, "count": count})
        response.raise_for_status()
        return response.json()

    def get_match_detail(self, match_id):
        url = f"https://{self.region}.api.riotgames.com/lol/match/v5/matches/{match_id}"
        response = self._get(url)
        response.raise_for_status()
        return response.json()
