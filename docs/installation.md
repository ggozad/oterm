## Installation

!!! note
    `oterm` works with multiple LLM providers — local and hosted. For local models, point it at [Ollama](https://github.com/ollama/ollama?tab=readme-ov-file#ollama), [vLLM](https://docs.vllm.ai/), [LM Studio](https://lmstudio.ai/), [llama.cpp](https://github.com/ggml-org/llama.cpp), or any OpenAI-compatible runner. For hosted providers (OpenAI, Anthropic, Groq, …), set the relevant API key. See [Providers and API keys](app_config.md#providers-and-api-keys) and the [`openaiCompatible`](app_config.md#openaicompatible-custom-openai-compatible-endpoints) config block.

=== "uvx"

    ```bash
    uvx oterm
    ```

=== "brew (macOS)"

    ```bash
    brew install oterm
    ```

    !!! note
        Since version `0.13.1`, `oterm` is in the official `homebrew/core` repository. If you have installed `oterm` by tapping `ggozad/formulas` you can now remove the tap and reinstall `oterm`.

=== "yay (Arch)"

    Maintained by [Daniel Chesters](https://github.com/DanielChesters).

    ```bash
    yay -S oterm
    ```

=== "nix-env (NixOS)"

    Maintained by [Gaël James](https://github.com/gaelj).

    ```bash
    nix-env -iA nixpkgs.oterm
    ```

=== "pip"

    ```bash
    pip install oterm
    ```

=== "pkg (FreeBSD)"

    Maintained by [Nicola Vitale](https://github.com/nivit).

    ```bash
    pkg install misc/py-oterm
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

=== "pip"

    ```bash
    pip install --upgrade oterm
    ```

=== "pkg (FreeBSD)"

    ```bash
    pkg upgrade misc/py-oterm
    ```
