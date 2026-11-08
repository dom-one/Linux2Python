import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "_data_wc35")
GNU = r"E:\software\Git\Git\usr\bin\wc.exe"

os.makedirs(DATA, exist_ok=True)

with open(os.path.join(DATA, "long.txt"), "wb") as handle:
    handle.write(b"x" * 19 + b"\n")
with open(os.path.join(DATA, "short.txt"), "wb") as handle:
    handle.write(b"z\n")

env = dict(os.environ)
env["LC_ALL"] = "C.UTF-8"

for args in (
    ["-L", "long.txt", "short.txt"],
    ["-lwc", "long.txt", "short.txt"],
    ["-c", "long.txt", "short.txt"],
    ["-lwc", "short.txt", "long.txt"],
):
    proc = subprocess.run(
        [GNU] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=DATA,
    )
    out = proc.stdout.decode("utf-8", "replace")
    print(args, repr(out))
    print("   " + out.replace(" ", "·").replace("\n", "¶\n"))
