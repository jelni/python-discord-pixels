import os
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, TypeVar

import httpx
from PIL import Image


_T = TypeVar('_T')


@dataclass
class Pixel:
    x: int
    y: int
    color: str

    def to_dict(self) -> dict:
        return {'x': self.x, 'y': self.y, 'rgb': self.color}


class Worker:
    def __init__(self, token: Optional[str]):
        self.token = token
        self.client = httpx.Client(
            base_url='https://pixels.pythondiscord.com/',
            headers={'Authorization': f'Bearer {token}'}
        )
        self.rate_limit = None

    def get_pixels(self) -> Image:
        r = self.client.request('GET', 'get_pixels')
        size = self.get_size()
        return Image.frombytes('RGB', size, r.content)

    def get_size(self) -> (int, int):
        r = self.client.request('GET', 'get_size', headers={})
        json = r.json()
        return json['width'], json['height']

    def set_pixel(self, pixel: Pixel) -> dict:
        r = self.client.request('POST', 'set_pixel', json=pixel.to_dict())
        self.rate_limit = self.process_cooldown(r.headers)
        json = r.json()
        print(json.get('message', json))
        return json

    def is_rate_limited(self, when: datetime) -> bool:
        if self.rate_limit is None:
            return False

        return self.rate_limit > when

    @staticmethod
    def process_cooldown(headers: httpx.Headers) -> Optional[datetime]:
        now = datetime.utcnow()
        seconds = None

        if 'Requests-Remaining' in headers:
            if int(headers['Requests-Remaining']) <= 0:
                seconds = float(headers['Requests-Reset'])
            else:
                return None

        if 'Cooldown-Reset' in headers:
            print('Sending requests too fast, hit the cooldown')
            seconds = float(headers['Cooldown-Reset'])

        if 'Retry-After' in headers:
            print('Rate limited by Cloudflare')
            seconds = float(headers['Retry-After'])

        if seconds:
            return now + timedelta(seconds=seconds)


class PainTer:
    def __init__(self, pattern: Image, workers: list[Worker]):
        self.pattern = pattern
        self.workers = workers

    def run(self):
        while True:
            queue = self.find_bad_pixels()

            if not queue:
                print('All pixels are correct!')
                time.sleep(60)
                continue

            print(f'{len(queue)} pixels queued')

            for worker in self.workers:
                while queue and not worker.is_rate_limited(datetime.utcnow()):
                    worker.set_pixel(pop_random(queue))
                    time.sleep(5)

            now = datetime.utcnow()
            if any(not worker.is_rate_limited(now) for worker in self.workers):
                continue
            sleep_time = min(worker.rate_limit - now for worker in self.workers).total_seconds()
            if sleep_time > 5:
                sleep_time += 2
            print(f'Sleeping {sleep_time:.1f}s')
            time.sleep(sleep_time)

    def find_bad_pixels(self) -> list[Pixel]:
        worker = random.choice(self.workers)
        current = worker.get_pixels()

        if self.pattern.size != current.size:
            current = current.crop((0, 0) + self.pattern.size)

        pattern_data = self.pattern.getdata()
        current_data = current.getdata()

        bad_pixels = []
        for i, (pattern_pixel, current_pixel) in enumerate(zip(pattern_data, current_data)):
            if pattern_pixel[3] == 0:  # transparent
                continue

            if pattern_pixel[:3] != current_pixel:
                bad_pixels.append(Pixel(i % current.width, i // current.width, rgb2hex(*pattern_pixel[:3])))

        return bad_pixels


def rgb2hex(r: int, g: int, b: int) -> str:
    return f'{r:02X}{g:02X}{b:02X}'


def pop_random(i: list[_T]) -> _T:
    return i.pop(random.randrange(len(i)))


def validate_image(image: Image) -> None:
    size = Worker(None).get_size()

    if image.width > size[0] or image.height > size[1]:
        raise Exception(f"image.png cannot be larger than {'×'.join(map(str, size))}")

    if image.mode != 'RGBA':
        raise Exception('image.png has to be an RGBA image')


def main():
    if len(sys.argv) > 1:
        tokens = sys.argv[1:]
    else:
        if 'PIXELS_TOKENS' in os.environ:
            tokens = os.environ['PIXELS_TOKENS'].split(':')
        else:
            raise Exception('Provide at least 1 token, or set the PIXELS_TOKENS environment variable')

    image = Image.open('image.png')
    validate_image(image)
    painter = PainTer(image, [Worker(token) for token in tokens])

    print(f'Using {len(painter.workers)} workers')

    try:
        painter.run()
    except KeyboardInterrupt:
        pass
    finally:
        return


if __name__ == '__main__':
    main()