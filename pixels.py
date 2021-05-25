import asyncio
import json
import os
import random
import sys
from datetime import datetime, timedelta
from typing import List, Tuple

import aiohttp
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


class JavaScriptator2000:
    base_url = 'https://pixels.pythondiscord.com'


    def __init__(self, tokens: List[str], pattern: List[List[str]], offset: Tuple[int, int]):
        self.tokens = tokens
        self.pattern = pattern
        self.offset = offset

        self.queue = []
        self.queue_event = asyncio.Event()
        self.request_lock = asyncio.Lock()
        self.SIZE = (160, 90)


    async def queuer(self):
        while True:
            print('Updating all pixels')
            async with self.request_lock:
                async with aiohttp.request('GET', self.base_url + '/' + 'get_pixels', headers=self.random_auth()) as r:
                    image = Image.frombytes('RGB', self.SIZE, await r.content.read())

                queue = []

                for row_id, row in enumerate(self.pattern):
                    for col_id, pattern_color in enumerate(row):
                        pixel = Pixel(col_id + self.offset[0], row_id + self.offset[1], pattern_color)
                        canvas_color = image.getpixel((col_id + self.offset[0], row_id + self.offset[1]))
                        canvas_color = f'{canvas_color[0]:02x}{canvas_color[1]:02x}{canvas_color[2]:02x}'

                        if canvas_color != pixel.color:
                            queue.append(pixel)

                print(f'Found {len(queue)} pixels to fix')
                random.shuffle(queue)
                self.queue = queue

            if self.queue:
                self.queue_event.set()
            await asyncio.sleep(30)


    async def worker(self, worker_id: int, token: str):
        while True:
            await self.queue_event.wait()
            if not self.queue:
                print(f'[WORKER {worker_id}] Queue is empty')
                self.queue_event.clear()
                continue

            await self.request_lock.acquire()
            pixel = self.queue.pop()
            print(f'[WORKER {worker_id}] Setting pixel {pixel}')
            async with aiohttp.request(
                    'POST', self.base_url + '/' + 'set_pixel',
                    json=pixel.to_dict(),
                    headers=self.get_auth(token)
            ) as r:
                self.request_lock.release()
                requests_remaining = int(r.headers['requests-remaining'])
                requests_reset = int(r.headers['requests-reset'])
                if requests_remaining <= 0:
                    print(
                        f'[WORKER {worker_id}] Sleeping {requests_reset}s to '
                        f'{(datetime.utcnow() + timedelta(seconds=requests_reset)).strftime("%H:%M:%S")}'
                    )
                    await asyncio.sleep(requests_reset)


    @staticmethod
    def get_auth(token: str):
        return {'Authorization': f'Bearer {token}'}


    def random_auth(self):
        return self.get_auth(random.choice(self.tokens))


    def run(self, loop: asyncio.AbstractEventLoop):
        print(f'Starting {len(self.tokens)} workers')
        loop.create_task(self.queuer())
        for i, token in enumerate(self.tokens):
            loop.create_task(self.worker(i + 1, token))


def main():
    with open('jslogo.json') as f:
        logo_pixels = json.loads(f.read())

    js = JavaScriptator2000(sys.argv[1:], logo_pixels, (122, 33))

    loop = asyncio.get_event_loop()
    js.run(loop)
    loop.run_forever()


if __name__ == '__main__':
    main()