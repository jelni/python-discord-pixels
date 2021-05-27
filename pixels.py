import asyncio
import os
import random
import sys
from datetime import datetime, timedelta
from typing import List, Tuple

import aiohttp
import requests
from PIL import Image


if os.name == 'nt':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class Pixel:
    def __init__(self, x: int, y: int, color: str):
        self.x = x
        self.y = y
        self.color = color


    def to_dict(self) -> dict:
        return {'x': self.x, 'y': self.y, 'rgb': self.color}


    def __str__(self):
        return f'x={self.x}, y={self.y}: {self.color}'


class PainTer:
    base_url = 'https://pixels.pythondiscord.com/'


    def __init__(self, pattern: Image, tokens: List[str]):
        self.pattern = pattern
        self.tokens = tokens

        self.queue = []
        self.queue_event = asyncio.Event()


    async def queuer(self):
        while True:
            self.queue_event.clear()
            async with aiohttp.request('GET', self.base_url + 'get_pixels', headers=self.random_auth()) as r:
                current = Image.frombytes('RGB', self.pattern.size, await r.content.read())

            queue = []
            pattern_data = self.pattern.getdata()
            current_data = current.getdata()

            for i, (pattern_pixel, current_pixel) in enumerate(zip(pattern_data, current_data)):
                if pattern_pixel[3] == 0:  # transparent
                    continue

                if pattern_pixel[:3] != current_pixel:
                    queue.append(Pixel(i % current.width, i // current.width, self.rgb2hex(*pattern_pixel[:3])))

            count = len(queue)
            print(f'Found {count} pixels to fix')
            self.queue = queue

            if self.queue:
                self.queue_event.set()

            await asyncio.sleep(30)


    async def worker(self, worker_id: int, token: str):
        while True:
            await self.queue_event.wait()
            if self.queue:
                pixel = self.queue.pop(random.randint(0, len(self.queue) - 1))
            else:
                self.queue_event.clear()
                self.worker_print(worker_id, 'Queue is empty')
                continue

            self.worker_print(worker_id, f'Setting pixel {pixel}')
            async with aiohttp.request(
                    'POST', self.base_url + 'set_pixel',
                    json=pixel.to_dict(),
                    headers=self.auth_header(token)
            ) as r:
                if r.headers['Content-Type'] != 'application/json':  # Cloudflare
                    time = int(r.headers['Retry-After'])
                    self.worker_print(worker_id, f'Cloudflare, sleeping {time}s')
                    await asyncio.sleep(time)
                    continue

                requests_remaining = int(r.headers['Requests-Remaining'])
                requests_reset = int(r.headers['Requests-Reset'])

            if requests_remaining <= 0:
                self.worker_print(
                    worker_id,
                    f'Sleeping {requests_reset}s '
                    f'to {(datetime.utcnow() + timedelta(seconds=requests_reset)).strftime("%H:%M:%S")}'
                )
                await asyncio.sleep(requests_reset)


    @staticmethod
    def auth_header(token: str) -> dict:
        return {'Authorization': f'Bearer {token}'}


    def random_auth(self) -> dict:
        return self.auth_header(random.choice(self.tokens))


    @staticmethod
    def rgb2hex(r: int, g: int, b: int) -> str:
        return f'{r:02x}{g:02x}{b:02x}'


    @staticmethod
    def worker_print(worker_id: int, text: str, **kwargs) -> None:
        print(f'[WORKER {worker_id}] ' + text, **kwargs)


    def run(self, loop: asyncio.AbstractEventLoop):
        print(f'Starting {len(self.tokens)} workers')
        loop.create_task(self.queuer())
        for i, token in enumerate(self.tokens):
            loop.create_task(self.worker(i + 1, token))


def get_size() -> Tuple[int, int]:
    r = requests.get(PainTer.base_url + 'get_size')
    payload = r.json()

    return payload['width'], payload['height']


def main():
    if len(sys.argv) > 1:
        tokens = sys.argv[1:]
    else:
        if 'PIXELS_TOKENS' in os.environ:
            tokens = os.environ['PIXELS_TOKENS'].split(':')
        else:
            raise Exception('Provide at least 1 token, or set the PIXELS_TOKENS environment variable')

    image = Image.open('image.png')

    size = get_size()

    if image.size != size:
        raise Exception(f"image.png has to be exacly {'×'.join(map(str, size))}")

    if image.mode != 'RGBA':
        raise Exception('image.png has to be an RGBA image')

    js = PainTer(image, tokens)

    loop = asyncio.get_event_loop()
    js.run(loop)
    loop.run_forever()


if __name__ == '__main__':
    main()