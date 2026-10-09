"""Exercise actual FetchContent, including Git, in disposable isolated fixtures."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile

cmake, build = sys.argv[1:]
work = Path(tempfile.mkdtemp(prefix="naval-task005-resolver-")).resolve()
environment = os.environ.copy()
config = work / "gitconfig"
config.write_text(
    f'[url "{(work / "repositories").as_uri()}/"]\n\tinsteadOf = https://github.com/NavalCommand/\n',
    encoding="utf-8",
)
environment.update(GIT_CONFIG_GLOBAL=str(config), GIT_CONFIG_NOSYSTEM="1")


def run(args, expected=0):
    result = subprocess.run(args, capture_output=True, text=True, env=environment)
    if (result.returncode == 0) != (expected == 0):
        raise RuntimeError(f"{args}\n{result.stdout}\n{result.stderr}")
    return result.stdout + result.stderr


include = f'include("{Path(build).as_posix()}/NavalCommand.Build.CMake.cmake")\n'
url_a = "https://github.com/NavalCommand/Fixture.A.git"
url_b = "https://github.com/NavalCommand/Fixture.B.git"
header = "cmake_minimum_required(VERSION 4.2)\nproject(Fixture LANGUAGES NONE)\n"
for name, body in [
    ("Fixture.B", 'file(WRITE "${CMAKE_BINARY_DIR}/b-marker" "git")\n'),
    ("Fixture.A", f"NavalCommandAddDependency({url_b} main)\n"),
]:
    repo = work / "repositories" / f"{name}.git"
    repo.mkdir(parents=True)
    (repo / "CMakeLists.txt").write_text(header + include + body)
    run(["git", "init", "-b", "main", str(repo)])
    run(["git", "-C", str(repo), "add", "."])
    run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Resolver Test",
            "-c",
            "user.email=resolver@example.invalid",
            "commit",
            "-m",
            "Fixture",
        ]
    )
local_b = work / "local-b"
local_b.mkdir()
(local_b / "CMakeLists.txt").write_text(
    header + 'file(WRITE "${CMAKE_BINARY_DIR}/b-marker" "local")\n'
)


def configure(name, registrations="", body="", expected=0):
    source = work / name
    source.mkdir()
    (source / "CMakeLists.txt").write_text(
        header + include + body + f"NavalCommandAddDependency({url_a} main)\n"
    )
    if registrations:
        (source / "Build.Local.cmake").write_text(registrations)
    output = run(
        [cmake, "-S", str(source), "-B", str(source / "o"), "-G", "Ninja"], expected
    )
    print(f"PASS {name}")
    return source, output


source, _ = configure("git-without-local")
assert (source / "o/b-marker").read_text() == "git"
entries = (source / "o/dependency-resolution.log").read_text()
assert "fixture.a" in entries and "fixture.b" in entries
names = [p.name for p in (source / "o/_deps").iterdir()]
assert all(len(n.split("-")[0]) == 15 for n in names)
assert not any("subbuild" in n for n in names)
print("PASS hashed names and CMP0168 NEW (no subbuild directories)")

a_path = (work / "repositories/Fixture.A.git").as_posix()
b_path = local_b.as_posix()
register_a = f'NavalCommandSetDependencyPath({url_a} "{a_path}")\n'
register_b = f'NavalCommandSetDependencyPath({url_b} "{b_path}")\n'
source, _ = configure("direct-and-transitive-local", register_a + register_b)
assert (source / "o/b-marker").read_text() == "local"
source, _ = configure("git-direct-local-transitive", register_b)
assert (source / "o/b-marker").read_text() == "local"
configure(
    "invalid-explicit",
    f'NavalCommandSetDependencyPath({url_a} "{work.as_posix()}/missing")\n',
    expected=1,
)
_, output = configure(
    "conflict",
    register_a + f'NavalCommandSetDependencyPath({url_a} "{b_path}")\n',
    expected=1,
)
assert "Conflicting local dependency registrations" in output
configure("same-registration", register_a + register_a)
_, output = configure(
    "late-registration",
    body=f"NavalCommandAddDependency({url_a} main)\n" + register_a,
    expected=1,
)
assert "must precede FetchContent_Declare" in output
_, output = configure(
    "conflicting-tags",
    body=f"NavalCommandAddDependency({url_a} main)\nNavalCommandAddDependency({url_a} other)\n",
    expected=1,
)
assert "Conflicting Git references" in output
configure(
    "canonical-identity",
    body=f"NavalCommandAddDependency({url_a} main)\nNavalCommandAddDependency(https://github.com/NavalCommand/Fixture.A main)\n",
)
print(f"RESOLUTION_PASS fixtures={work}")
