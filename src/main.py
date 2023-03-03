import random
import re
import sys
import json
import textwrap
import time
import logging.config
from pathlib import Path
from urllib.parse import quote, urlencode, parse_qs, urlsplit, urlunsplit

import asyncio
import aiohttp
import requests

reset = '\u001b[0m'
colors = [f'\u001b[{i}m' for i in range(30, 38)]
logging.config.dictConfig({
    "version": 1,
    "formatters": {
        "simple": {
            "format": "%(levelname)s: %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "simple",
            "stream": "ext://sys.stdout"
        },
        "file": {
            "class": "logging.FileHandler",
            "level": "DEBUG",
            "formatter": "simple",
            "filename": "debug.log",
            "encoding": "utf8",
            "mode": "a"
        }
    },
    "loggers": {
        "myLogger": {
            "level": "DEBUG",
            "handlers": [
                "console"
            ],
            "propagate": "no"
        }
    },
    "root": {
        "level": "DEBUG",
        "handlers": [
            "console",
            "file"
        ]
    }
})
logger = logging.getLogger(__name__)

try:
    if get_ipython().__class__.__name__ == 'ZMQInteractiveShell':
        import nest_asyncio
        nest_asyncio.apply()
except:
    ...

if sys.platform != 'win32':
    try:
        import uvloop

        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    except:
        ...
else:
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def search(*args, config: dict, out: str = 'data'):
    out_path = make_output_dirs(out)
    return asyncio.run(process(args, config, out_path))


async def process(queries: tuple, config: dict, out: Path) -> tuple:
    conn = aiohttp.TCPConnector(limit=len(queries), ssl=False)
    async with aiohttp.ClientSession(headers=get_headers(), connector=conn) as s:
        return await asyncio.gather(*(paginate(q, s, config, out) for q in queries))


async def paginate(query: str, session: aiohttp.ClientSession, config: dict, out: Path) -> list[dict]:
    api = 'https://api.twitter.com/2/search/adaptive.json?'
    config['q'] = query
    data, next_cursor = await backoff(lambda: get(session, api, config), query)
    all_data = []
    c = colors.pop() if colors else ''
    while next_cursor:
        logger.debug(f'{c}{query}{reset}')
        config['cursor'] = next_cursor
        data, next_cursor = await backoff(lambda: get(session, api, config), query)
        data['query'] = query
        (out / f'raw/{time.time_ns()}.json').write_text(json.dumps(data, indent=4))
        all_data.append(data)
    return all_data


async def backoff(fn, info, retries=12):
    for i in range(retries + 1):
        try:
            data, next_cursor = await fn()
            if not data.get('globalObjects', {}).get('tweets'):
                raise Exception
            return data, next_cursor
        except Exception as e:
            if i == retries:
                logger.debug(f'Max retries exceeded\n{e}')
                return
            t = 2 ** i + random.random()
            logger.debug(f'No data for: \u001b[1m{info}\u001b[0m | retrying in {f"{t:.2f}"} seconds\t\t{e}')
            time.sleep(t)


async def get(session: aiohttp.ClientSession, api: str, params: dict) -> tuple[dict, str]:
    url = set_qs(api, params, update=True)
    r = await session.get(url)
    data = await r.json()
    next_cursor = get_cursor(data)
    return data, next_cursor


def get_cursor(res: dict):
    try:
        for instr in res['timeline']['instructions']:
            if replaceEntry := instr.get('replaceEntry'):
                cursor = replaceEntry['entry']['content']['operation']['cursor']
                if cursor['cursorType'] == 'Bottom':
                    return cursor['value']
                continue
            for entry in instr['addEntries']['entries']:
                if entry['entryId'] == 'cursor-bottom-0':
                    return entry['content']['operation']['cursor']['value']
    except Exception as e:
        logger.debug(e)


def set_qs(url: str, qs: dict, update=False) -> str:
    *_, q, f = urlsplit(url)
    return urlunsplit((*_, urlencode(qs | parse_qs(q) if update else qs, doseq=True, quote_via=quote, safe='()'), f))


def get_headers(fname: str = None) -> dict:
    if fname:
        with open(fname) as fp:
            return {y.group(): z.group()
                    for x in fp.read().splitlines()
                    if (y := re.search('^[\w-]+(?=:\s)', x),
                        z := re.search(f'(?<={y.group()}:\s).*', x))}
    # default
    headers = {
        'authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    r = requests.post('https://api.twitter.com/1.1/guest/activate.json', headers=headers)
    headers['x-guest-token'] = r.json()['guest_token']
    return headers


def make_output_dirs(path: str) -> Path:
    p = Path(path)
    (p / 'raw').mkdir(parents=True, exist_ok=True)
    (p / 'processed').mkdir(parents=True, exist_ok=True)
    (p / 'final').mkdir(parents=True, exist_ok=True)
    return p


def main() -> int:
    sys.stdout.write(textwrap.dedent(r'''
       __           _ __  __                                         __  
      / /__      __(_) /_/ /____  _____   ________  ____ ___________/ /_ 
     / __/ | /| / / / __/ __/ _ \/ ___/  / ___/ _ \/ __ `/ ___/ ___/ __ \
    / /_ | |/ |/ / / /_/ /_/  __/ /     (__  )  __/ /_/ / /  / /__/ / / /
    \__/ |__/|__/_/\__/\__/\___/_/     /____/\___/\__,_/_/   \___/_/ /_/ 


    '''))
    search(*sys.argv[1:], config={
        "include_profile_interstitial_type": 1,
        "include_blocking": 1,
        "include_blocked_by": 1,
        "include_followed_by": 1,
        "include_want_retweets": 1,
        "include_mute_edge": 1,
        "include_can_dm": 1,
        "include_can_media_tag": 1,
        "include_ext_has_nft_avatar": 1,
        "include_ext_is_blue_verified": 1,
        "include_ext_verified_type": 1,
        "skip_status": 1,
        "cards_platform": "Web-12",
        "include_cards": 1,
        "include_ext_alt_text": "true",
        "include_ext_limited_action_results": "false",
        "include_quote_count": "true",
        "include_reply_count": 1,
        "tweet_mode": "extended",
        "include_ext_collab_control": "true",
        "include_ext_views": "true",
        "include_entities": "true",
        "include_user_entities": "true",
        "include_ext_media_color": "true",
        "include_ext_media_availability": "true",
        "include_ext_sensitive_media_warning": "true",
        "include_ext_trusted_friends_metadata": "true",
        "send_error_codes": "true",
        "simple_quoted_tweet": "true",
        "query_source": "typed_query",
        "count": 100,
        "q": "",
        "requestContext": "launch",
        "pc": 1,
        "spelling_corrections": 1,
        "include_ext_edit_control": "true",
        "ext": "mediaStats,highlightedLabel,hasNftAvatar,voiceInfo,birdwatchPivot,enrichments,superFollowMetadata,unmentionInfo,editControl,collab_control,vibe"
    })
    return 0


if __name__ == '__main__':
    exit(main())
