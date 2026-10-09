"""Exercise actual FetchContent, including Git, in disposable isolated fixtures."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile

cmake_executable, build_repository = sys.argv[1:]
fixture_directory = Path(tempfile.mkdtemp(prefix="naval-task005-resolver-")).resolve()
environment = os.environ.copy()
git_config_path = fixture_directory / "gitconfig"
git_config_path.write_text(
    f'[url "{(fixture_directory / "repositories").as_uri()}/"]\n\tinsteadOf = https://github.com/NavalCommand/\n',
    encoding="utf-8",
)
environment.update(GIT_CONFIG_GLOBAL=str(git_config_path), GIT_CONFIG_NOSYSTEM="1")


def run(arguments, expected=0):
    result = subprocess.run(arguments, capture_output=True, text=True, env=environment)
    if (result.returncode == 0) != (expected == 0):
        raise RuntimeError(f"{arguments}\n{result.stdout}\n{result.stderr}")
    return result.stdout + result.stderr


include = (
    f'include("{Path(build_repository).as_posix()}/NavalCommand.Build.CMake.cmake")\n'
)
direct_dependency_url = "https://github.com/NavalCommand/Fixture.A.git"
transitive_dependency_url = "https://github.com/NavalCommand/Fixture.B.git"
header = "cmake_minimum_required(VERSION 4.2)\nproject(Fixture LANGUAGES NONE)\n"
for name, body in [
    ("Fixture.B", 'file(WRITE "${CMAKE_BINARY_DIR}/b-marker" "git")\n'),
    ("Fixture.A", f"NavalCommandAddDependency({transitive_dependency_url} main)\n"),
]:
    fixture_repository = fixture_directory / "repositories" / f"{name}.git"
    fixture_repository.mkdir(parents=True)
    (fixture_repository / "CMakeLists.txt").write_text(header + include + body)
    run(["git", "init", "-b", "main", str(fixture_repository)])
    run(["git", "-C", str(fixture_repository), "add", "."])
    run(
        [
            "git",
            "-C",
            str(fixture_repository),
            "-c",
            "user.name=Resolver Test",
            "-c",
            "user.email=resolver@example.invalid",
            "commit",
            "-m",
            "Fixture",
        ]
    )
local_transitive_repository = fixture_directory / "local-b"
local_transitive_repository.mkdir()
(local_transitive_repository / "CMakeLists.txt").write_text(
    header + 'file(WRITE "${CMAKE_BINARY_DIR}/b-marker" "local")\n'
)


def configure(name, registrations="", body="", expected=0):
    source = fixture_directory / name
    source.mkdir()
    (source / "CMakeLists.txt").write_text(
        header
        + include
        + body
        + f"NavalCommandAddDependency({direct_dependency_url} main)\n"
    )
    if registrations:
        (source / "Build.Local.cmake").write_text(registrations)
    output = run(
        [cmake_executable, "-S", str(source), "-B", str(source / "o"), "-G", "Ninja"],
        expected,
    )
    print(f"PASS {name}")
    return source, output


source, _ = configure("git-without-local")
assert (source / "o/b-marker").read_text() == "git"
entries = (source / "o/dependency-resolution.log").read_text()
assert "fixture.a" in entries and "fixture.b" in entries
names = [dependency_path.name for dependency_path in (source / "o/_deps").iterdir()]
assert all(len(dependency_name.split("-")[0]) == 15 for dependency_name in names)
assert not any("subbuild" in dependency_name for dependency_name in names)
print("PASS hashed names and CMP0168 NEW (no subbuild directories)")

direct_checkout_path = (fixture_directory / "repositories/Fixture.A.git").as_posix()
transitive_checkout_path = local_transitive_repository.as_posix()
direct_registration = (
    f'NavalCommandSetDependencyPath({direct_dependency_url} "{direct_checkout_path}")\n'
)
transitive_registration = f'NavalCommandSetDependencyPath({transitive_dependency_url} "{transitive_checkout_path}")\n'
source, _ = configure(
    "direct-and-transitive-local", direct_registration + transitive_registration
)
assert (source / "o/b-marker").read_text() == "local"
source, _ = configure("git-direct-local-transitive", transitive_registration)
assert (source / "o/b-marker").read_text() == "local"
configure(
    "invalid-explicit",
    f'NavalCommandSetDependencyPath({direct_dependency_url} "{fixture_directory.as_posix()}/missing")\n',
    expected=1,
)
_, output = configure(
    "conflict",
    direct_registration
    + f'NavalCommandSetDependencyPath({direct_dependency_url} "{transitive_checkout_path}")\n',
    expected=1,
)
assert "Conflicting local dependency registrations" in output
configure("same-registration", direct_registration + direct_registration)
_, output = configure(
    "late-registration",
    body=f"NavalCommandAddDependency({direct_dependency_url} main)\n"
    + direct_registration,
    expected=1,
)
assert "must precede FetchContent_Declare" in output
_, output = configure(
    "conflicting-tags",
    body=f"NavalCommandAddDependency({direct_dependency_url} main)\nNavalCommandAddDependency({direct_dependency_url} other)\n",
    expected=1,
)
assert "Conflicting Git references" in output
configure(
    "canonical-identity",
    body=f"NavalCommandAddDependency({direct_dependency_url} main)\nNavalCommandAddDependency(https://github.com/NavalCommand/Fixture.A main)\n",
)
print(f"RESOLUTION_PASS fixtures={fixture_directory}")
