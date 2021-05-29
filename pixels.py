import asyncio
import os
import random
import sys
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import aiohttp
import requests
from PIL import Image
from multidict import CIMultiDictProxy


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


    def __init__(self, pattern: Image, tokens: List[str], loop: asyncio.AbstractEventLoop):
        self.pattern = pattern
        self.tokens = tokens
        self.loop = loop

        self.running = True
        self.queue = []
        self.queue_event = asyncio.Event()


    async def queuer(self):
        while self.running:
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
        while self.running:
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
                time = self.process_cooldown(r.headers)

            if time:
                self.worker_print(
                    worker_id,
                    f'Sleeping {time}s '
                    f'to {(datetime.utcnow() + timedelta(seconds=time)).strftime("%H:%M:%S")}'
                )
                await asyncio.sleep(time)
            await asyncio.sleep(random.random())


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


    @staticmethod
    def process_cooldown(headers: CIMultiDictProxy[str]) -> Optional[float]:
        if 'Requests-Remaining' in headers:
            if int(headers['Requests-Remaining']) <= 0:
                return float(headers['Requests-Reset'])
            else:
                return None

        if 'Cooldown-Reset' in headers:
            print('Sending requests too fast, hit the cooldown')
            return float(headers['Cooldown-Reset'])

        if 'Retry-After' in headers:
            print('Rate limited by Cloudflare')
            return float(headers['Retry-After'])

        return None


    def run(self):
        print(f'Starting {len(self.tokens)} workers')

        self.loop.create_task(self.queuer())
        for i, token in enumerate(self.tokens):
            self.loop.create_task(self.worker(i + 1, token))

        self.loop.run_forever()


    def stop(self):
        self.running = False
        print('Stopping')
        self.loop.stop()


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

    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)
    painter = PainTer(image, tokens, loop)

    try:
        painter.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(e)
    finally:
        painter.stop()


if __name__ == '__main__':
    main()