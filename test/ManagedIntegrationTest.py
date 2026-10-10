"""Real FetchContent and MSBuild graphs; all generated fixtures stay under o/."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as xml

cmake, build_repository = sys.argv[1:]
build_repository = Path(build_repository).resolve()
fixture_root = build_repository / "o" / "managed-tests"
fixture_root.mkdir(parents=True, exist_ok=True)
fixture = Path(tempfile.mkdtemp(prefix="run-", dir=fixture_root))
environment = os.environ.copy()
git_config = fixture / "gitconfig"
git_config.write_text(
    f'[url "{(fixture / "repositories").as_uri()}/"]\n'
    '\tinsteadOf = https://github.com/NavalCommand/\n',
    encoding="utf-8",
)
environment.update(GIT_CONFIG_GLOBAL=str(git_config), GIT_CONFIG_NOSYSTEM="1")
dependency_url = "https://github.com/NavalCommand/Managed.Dependency.git"
middle_url = "https://github.com/NavalCommand/Managed.Middle.git"


def run(arguments, succeeds=True):
    result = subprocess.run(arguments, capture_output=True, text=True, env=environment)
    output = result.stdout + result.stderr
    if (result.returncode == 0) != succeeds:
        raise RuntimeError(f"{arguments}\n{output}")
    return output


def create_module(path, name, dependency=None):
    (path / "managed").mkdir(parents=True)
    (path / "CMakeLists.txt").write_text(
        'cmake_minimum_required(VERSION 4.2)\n'
        f'project({name} LANGUAGES NONE)\n'
        f'include("{build_repository.as_posix()}/NavalCommand.Build.CMake.cmake")\n'
        + (f'NavalCommandAddDependency({dependency} main)\n' if dependency else "")
        + 'NavalCommandConfigureModule()\n'
    )
    context = 'NavalCommandManagedContext("FixtureInput=${FIXTURE_INPUT}"'
    references = ""
    if dependency:
        context = (
            f'NavalCommandGetDependencySource({dependency} dependencySource)\n'
            + context + ' "ManagedDependency=${dependencySource}"'
        )
        dependency_name = "Managed.Middle" if dependency == middle_url else "Managed.Dependency"
        references = (
            f'<ItemGroup><ProjectReference Include="$(ManagedDependency)/managed/{dependency_name}.csproj" /></ItemGroup>'
        )
    (path / "managed/CMakeLists.txt").write_text(
        context + ')\n' + f'NavalCommandAddManagedProject({name}.Managed {name}.csproj)\n'
    )
    (path / "managed" / f"{name}.csproj").write_text(
        '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup>'
        '<TargetFramework>net10.0</TargetFramework></PropertyGroup>'
        + references + '</Project>\n'
    )
    (path / "managed/Value.cs").write_text(
        f'namespace {name};\npublic static class Value\n{{\n    public const int Number = 7;\n}}\n'
    )
    (path / "Directory.Build.props").write_text(
        '<Project>\n  <PropertyGroup>\n'
        '    <BaseOutputPath>$(MSBuildThisFileDirectory)o/managed/$(MSBuildProjectName)/bin/</BaseOutputPath>\n'
        '    <BaseIntermediateOutputPath>$(MSBuildThisFileDirectory)o/managed/$(MSBuildProjectName)/obj/</BaseIntermediateOutputPath>\n'
        '  </PropertyGroup>\n'
        '  <Import Project="$(MSBuildThisFileDirectory)o/managed/Build.Context.props" />\n'
        '</Project>\n'
    )
    (path / "Directory.Build.targets").write_text(
        '<Project><Import Project="$(NavalCommandManagedTargets)" /></Project>\n'
    )


for name, dependency in [("Managed.Dependency", None), ("Managed.Middle", dependency_url)]:
    repository = fixture / "repositories" / (name + ".git")
    create_module(repository, name, dependency)
    run(["git", "init", "-b", "main", str(repository)])
    run(["git", "-C", str(repository), "add", "."])
    run(["git", "-C", str(repository), "-c", "user.name=Build Test",
         "-c", "user.email=build@example.invalid", "commit", "-m", "Fixture"])

for mode in ["git", "local"]:
    consumer = fixture / mode
    create_module(consumer, "Managed.Consumer", middle_url)
    if mode == "local":
        (consumer / "Build.Local.cmake").write_text(
            f'NavalCommandSetDependencyPath({middle_url} "{(fixture / "repositories/Managed.Middle.git").as_posix()}")\n'
            f'NavalCommandSetDependencyPath({dependency_url} "{(fixture / "repositories/Managed.Dependency.git").as_posix()}")\n'
        )
    binary = consumer / "o/native"
    run([cmake, "-S", str(consumer), "-B", str(binary), "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release"])
    for configuration in ["Debug", "Release"]:
        run(["dotnet", "build", str(consumer / "managed/Managed.Consumer.csproj"), "-c", configuration])
        target_record = consumer / f"o/managed/Managed.Consumer/bin/{configuration}/TargetPath.txt"
        assert Path(target_record.read_text(encoding="utf-8-sig").strip()).exists()
    run([cmake, "--build", str(binary), "--target", "Managed.Consumer.Managed"])
    context = xml.parse(consumer / "o/managed/Build.Context.props")
    middle_source = Path(context.findtext("PropertyGroup/ManagedDependency"))
    assert (middle_source / "managed/Managed.Middle.csproj").exists()
    middle_context = xml.parse(middle_source / "o/managed/Build.Context.props")
    dependency_source = Path(middle_context.findtext("PropertyGroup/ManagedDependency"))
    assert (dependency_source / "managed/Managed.Dependency.csproj").exists()
    sources = [consumer] + [path.parent.parent for path in binary.glob("_deps/*-src/managed/*.csproj")]
    for source in sources:
        assert not list((source / "managed").glob("bin"))
        assert not list((source / "managed").glob("obj"))
    print(f"PASS {mode}: direct + transitive contexts, direct Debug/Release MSBuild and CMake target")
    conflict = run([cmake, "-S", str(consumer), "-B", str(binary), "-DFIXTURE_INPUT=changed"], succeeds=False)
    assert "Managed context conflict" in conflict
    run([cmake, "-S", str(consumer), "-B", str(binary), "-DFIXTURE_INPUT=changed",
         "-DNAVALCOMMAND_REPLACE_MANAGED_CONTEXT=ON"])
    run(["dotnet", "build", str(consumer / "managed/Managed.Consumer.csproj"), "-c", "Release"])
    print(f"PASS {mode}: conflicting consumer rejected and explicit IDE context replacement verified")
    other_binary = consumer / "o/other-consumer"
    run([cmake, "-S", str(consumer), "-B", str(other_binary), "-G", "Ninja",
         "-DCMAKE_BUILD_TYPE=Debug", "-DFIXTURE_INPUT=other",
         "-DNAVALCOMMAND_REPLACE_MANAGED_CONTEXT=ON"])
    stale_output = run([cmake, "--build", str(binary), "--target", "Managed.Consumer.Managed"], succeeds=False)
    assert "Managed context conflict" in stale_output or "compare_files" in stale_output
    run(["dotnet", "build", str(consumer / "managed/Managed.Consumer.csproj"), "-c", "Debug"])
    run([cmake, "-S", str(consumer), "-B", str(binary), "-DNAVALCOMMAND_REPLACE_MANAGED_CONTEXT=ON"])
    run([cmake, "--build", str(binary), "--target", "Managed.Consumer.Managed"])
    assert "NAVALCOMMAND_REPLACE_MANAGED_CONTEXT:BOOL=OFF" in (binary / "CMakeCache.txt").read_text()
    print(f"PASS {mode}: stale CMake consumer rejected; direct IDE uses selected context; replacement resets")

print(f"MANAGED_INTEGRATION_PASS fixtures={fixture}")
