# Installation

!!! note
    `oterm` works with local and hosted LLM providers. For local models, point it at [Ollama](https://github.com/ollama/ollama?tab=readme-ov-file#ollama), [vLLM](https://docs.vllm.ai/), [LM Studio](https://lmstudio.ai/), [llama.cpp](https://github.com/ggml-org/llama.cpp), or any OpenAI-compatible runner. For hosted providers (OpenAI, Anthropic, Groq, …), set the relevant API key. See [Providers and API keys](app_config.md#providers-and-api-keys) and the [`openaiCompatible`](app_config.md#openaicompatible-custom-openai-compatible-endpoints) config block.

=== "uvx"

    ```bash
    uvx oterm
    ```

=== "brew (macOS)"

    ```bash
    brew install oterm
    ```

=== "yay (Arch)"

    Community package maintained by [Rafael Dominiquini](https://github.com/Dominiquini), published as [`oterm` on the AUR](https://aur.archlinux.org/packages/oterm). May lag behind the latest release.

    ```bash
    yay -S oterm
    ```

=== "nix-env (NixOS)"

    Community package maintained by [Gaël James](https://github.com/gaelj), published as [`oterm` in nixpkgs](https://search.nixos.org/packages?channel=unstable&show=oterm). May lag behind the latest release.

    ```bash
    nix-env -iA nixpkgs.oterm
    ```

=== "pip"

    ```bash
    pip install oterm
    ```

=== "pkg (FreeBSD)"

    Community package maintained by [Nicola Vitale](https://github.com/nivit), published as [`misc/py-oterm` on FreshPorts](https://www.freshports.org/misc/py-oterm/). May lag behind the latest release.

    ```bash
    pkg install misc/py-oterm
    ```

### Community packages

The Arch, NixOS and FreeBSD packages are maintained outside this project by the people named above, so their version does not always match the [latest release on PyPI](https://pypi.org/project/oterm/). Run `oterm --version` after installing to see which version you got. If you need the current release, use `uvx oterm`, or `pip install --upgrade oterm`, which install from PyPI.

#### For packagers

The runtime dependencies are listed in [`pyproject.toml`](https://github.com/ggozad/oterm/blob/main/pyproject.toml) and in the [package metadata on PyPI](https://pypi.org/project/oterm/). Since 0.15 oterm depends on `pydantic-ai-slim`, with the provider extras enabled, and on `pydantic-ai-harness`; Python 3.11 or newer is required. The versions in `pyproject.toml` are pinned exactly so that a released version resolves to the same dependency set everywhere, and `uv.lock` records the full resolved set used in development. A distribution that carries a different version of a dependency can package oterm against that version and run the test suite to check it.

### Spoken responses

The [`speak`](tools/index.md#capabilities) capability needs the `speak` extra, which brings in `piper-tts` (GPL-3.0):

=== "uvx"

    ```bash
    uvx "oterm[speak]"
    ```

=== "pip"

    ```bash
    pip install "oterm[speak]"
    ```

## Updating oterm

Use the same package manager you installed with.

=== "uvx"

    ```bash
    uvx oterm@latest
    ```

=== "brew (macOS)"

    ```bash
    brew upgrade oterm
    ```

=== "yay (Arch)"

    ```bash
    yay -Syu oterm
    ```

=== "nix-env (NixOS)"

    ```bash
    nix-env -uA nixpkgs.oterm
    ```

=== "pip"

    ```bash
    pip install --upgrade oterm
    ```

=== "pkg (FreeBSD)"

    ```bash
    pkg upgrade misc/py-oterm
    ```
