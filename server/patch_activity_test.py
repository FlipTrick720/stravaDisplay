import re

with open("views/activity.py", "r") as f:
    src = f.read()

src = src.replace(
    '        "heartrate": {"data": heartrate_stream},\n    }',
    '        "heartrate": {"data": heartrate_stream},\n        "latlng": {"data": [[47.22 + 0.06 * (i/n) + 0.01 * math.sin((i/n)*9*math.pi), 11.28 + 0.18 * (i/n) + 0.01 * math.cos((i/n)*7*math.pi)] for i in range(n)]},\n    }'
)

with open("views/activity.py", "w") as f:
    f.write(src)
print("patched")
