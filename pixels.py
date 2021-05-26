import asyncio
import os
import random
import sys
from datetime import datetime, timedelta
from typing import List

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


    def __init__(self, goal: Image, tokens: List[str]):
        self.goal = goal
        self.tokens = tokens

        self.queue = []
        self.queue_event = asyncio.Event()
        self.SIZE = (160, 90)


    async def queuer(self):
        while True:
            self.queue_event.clear()
            async with aiohttp.request('GET', self.base_url + '/' + 'get_pixels', headers=self.random_auth()) as r:
                current = Image.frombytes('RGB', self.SIZE, await r.content.read())

            queue = []
            goal_data = self.goal.getdata()
            current_data = current.getdata()

            for i, (goal_pixel, current_pixel) in enumerate(zip(goal_data, current_data)):
                if goal_pixel[3] == 0:  # transparent
                    continue

                if goal_pixel[:3] != current_pixel:
                    queue.append(Pixel(i % current.width, i // current.width, self.rgb2hex(*goal_pixel[:3])))

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
                    'POST', self.base_url + '/' + 'set_pixel',
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


def main():
    image = Image.open('image.png')

    if image.size != (160, 90):
        raise Exception('image.png has to be exacly 160×90')

    if image.mode != 'RGBA':
        raise Exception('image.png has to be an RGBA image')

    js = JavaScriptator2000(image, sys.argv[1:])

    loop = asyncio.get_event_loop()
    js.run(loop)
    loop.run_forever()


if __name__ == '__main__':
    main()