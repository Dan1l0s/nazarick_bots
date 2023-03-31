from urllib.request import urlopen
import json
import re
import config
import asyncio


async def main():
    url = "http://anison.fm/status.php?widget=true"
    name = ""
    while True:
        response = urlopen(url)
        data_json = json.loads(response.read())
        duration = data_json["duration"] - 13
        if re.search("151; (.+?)</span>", data_json['on_air']).group(1) == name:
            await asyncio.sleep(duration - 1)
            continue
        name = re.search("151; (.+?)</span>", data_json['on_air']).group(1)
        author = re.search("blank'>(.+?)</a>", data_json['on_air']).group(1)
        print(f"{author} - {name}")
        await asyncio.sleep(duration - 1)

if __name__ == "__main__":
    asyncio.run(main())
