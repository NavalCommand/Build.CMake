# NavalCommand Build.CMake

Project-wide documentation is maintained in the separate **Docs Git repository**. Before changing this module, explicitly read [Docs/AGENTS.md](../Docs/AGENTS.md), [architecture](../Docs/ARCHITECTURE.md), [module/build policy](../Docs/MODULE_STRUCTURE.md), [local sources](../Docs/LOCAL_SOURCES.md), and [code style](../Docs/CODE_STYLE.md) with its [owner export](../Docs/CodeStyle.xml). The shared instructions are not discovered automatically across repository boundaries; do not create a competing AGENTS.md in the parent workspace. Historical reports and reproduction guides are indexed under [Docs/Tasks/](../Docs/Tasks/README.md), with run receipts under [Docs/Evidence/](../Docs/Evidence/README.md).


Shared build policy and canonical internal dependency resolution, modeled on [UnrealVoxelSim/ModuleTemplate](https://github.com/UnrealVoxelSim/ModuleTemplate) and [UnrealVoxelSim/Build.CMake](https://github.com/UnrealVoxelSim/Build.CMake). CMake 4.2+, Ninja, Git, vcpkg for external packages. No gameplay or runtime dependency.

Native module roots initialize their project, FetchContent `ncbuild`, include `NavalCommand.Build.CMake.cmake`, declare dependencies, then call `NavalCommandConfigureModule()`. Production targets live in src, reusable mocks in mock, tests in test, executables in app, optional benchmarks in benchmark. Existing target names are retained for compatibility.

```cmake
NavalCommandAddDependency(https://github.com/NavalCommand/Gateway.Api.git main)
```

The resolver derives identity from owner/repository, normalizes case and `.git`, and uses a deterministic 12-hex SHA-256 suffix (`nc_` + hash). The 15-character name bounds Windows dependency paths; CMP0168 is NEW. Repeated identities resolve once; conflicting Git tags, local registrations or a detected hash collision fail. Registered paths must exist and contain CMakeLists.txt. Changing an override after declaration fails.

Only the top-level ignored Build.Local.cmake is loaded, before any ordinary dependency declaration. Its global registrations are visible to direct and transitive dependencies. Fetched modules' developer files are never read.

```cmake
# Build.Local.cmake (ignored; use your actual absolute checkout path)
NavalCommandSetDependencyPath(
  https://github.com/NavalCommand/Gateway.Api.git
  "D:/Projects/NavalCommand/Gateway.Api")
```

Bootstrap Build.CMake itself with CMake's standard `-DFETCHCONTENT_SOURCE_DIR_NCBUILD=...` option. No implicit sibling search or workspace-root environment variable exists. Unregistered modules fetch their declared URL/tag. To refresh main, reconfigure normally; to reset overridden sources, use a fresh build tree or `cmake --fresh` with the same explicit bootstrap/dependency options. Do not edit generated `_deps` copies.

Presets contain configurePresets only: windows-msvc-debug/release and linux-clang-debug/release. Enter the corresponding compiler shell, then `cmake --preset windows-msvc-release`, `cmake --build o/windows-msvc-release`, `ctest --test-dir o/windows-msvc-release --output-on-failure --no-tests=error`. MSVC 2026 is preferred. C++26 policy is centralized; available features use MSVC /std:c++latest (CMake compiler-table override), /Zc:__cplusplus, exceptions and UTF-8. Full C++26 implementation is not assumed. Other compilers use their native CMake 26 mode. Windows uses x64-windows-static for target and host dependencies, with the static MSVC runtime (/MT in Release, /MTd in Debug). All linked native targets must use the matching runtime. Reconfigure with --fresh and rebuild when migrating an existing static-md build; its dependency prefix cannot be reused for the new triplet.

Build.CMake's own CTest suite uses disposable Git repositories under o/ and isolated Git URL rewriting to test actual FetchContent without publishing repositories: Git/no-local, direct/transitive overrides, mixed resolution, invalid/conflicting/late registrations, conflicting tags, normalized identities and short paths. Managed fixtures also exercise real transitive MSBuild builds, Debug/Release output isolation, context conflicts, explicit replacement and stale CMake consumer rejection.

## Managed build integration

Follow the authoritative [managed build policy](../Docs/MANAGED_BUILD.md). One CMake configure resolves internal source dependencies and persists each managed repository's ignored `o/managed/Build.Context.props`. Then ordinary `.csproj` builds in Visual Studio/Rider or `dotnet build ... -c Debug/Release` use those sources through real ProjectReferences without extra properties or another configure. Change source/tool/game-reference locations by reconfiguring, not by editing generated projects. Conflicting contexts require explicit `-DNAVALCOMMAND_REPLACE_MANAGED_CONTEXT=ON`; existing CMake consumers must then be reconfigured.

All repository-owned generated files stay under `o/`: native preset directories, per-project MSBuild `o/managed/<project>/{bin,obj}/` directories and mod `o/package`/`o/harness` stages. MSBuild preserves configuration/platform/framework dimensions. The shared helper discovers managed/CMakeLists.txt and invokes only the requested top-level project; MSBuild owns NuGet and transitive compilation. Game-reference absence blocks only requested game-dependent projects.
