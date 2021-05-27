# Python Discord Pixels

An asynchronous Python script made for the [Python Discord Pixels](https://pixels.pythondiscord.com/) event.

## Usage

- Create an `image.png` RGBA image with your pattern. Transparent pixels will be ignored.
- Get your token [here](https://pixels.pythondiscord.com/authorize).

```shell
pip install -r requirements.txt -U
python pixels.py token1 token2 ...
```

You can also set the `PIXELS_TOKENS` environment variable to `token1:token2:...` and run the script without any arguments.

It's not recommended to use more than 2 tokens, because you will get rate limited by Cloudflare.

## Heroku

You can run this script on [Heroku](https://heroku.com/). To do this add the `heroku/python` Buildpack and set the `PIXELS_TOKENS` environment variable.