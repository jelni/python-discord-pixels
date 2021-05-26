# Python Discord Pixels

An asynchronous Python script made for the [Python Discord Pixels](https://pixels.pythondiscord.com/) event.

## Usage

- Create a 160×90 RGBA `image.png` file with your pattern. Transparent pixels will be ignored.
- Get your token [here](https://pixels.pythondiscord.com/authorize).

```shell
pip install -r requirements.txt -U
python pixels.py token1 token2 ...
```

It's not recommended to use more than 2 tokens, because you will get rate limited by Cloudflare.