### Customizing models

When creating a new chat, you may not only select the model, but also customize the following:

-  `system` instruction prompt
- `tools` used. See [Tools](tools.md) for more information on how to make tools accessible.
- chat `parameters` (such as context length, seed, temperature etc) passed to the model. For a list of all supported parameters refer to the [Ollama documentation](https://github.com/ollama/ollama/blob/main/docs/modelfile.md#valid-parameters-and-values). 
-  Ouput `format`/structured output. In the format field you can specify either
   - nothing, in which case Ollama will return the output as text. 
   - use Ollama's *Structured Output* specifying the full format as JSON schema. See [here](https://ollama.com/blog/structured-outputs) for more information.

You can also "edit" an existing chat to change the system prompt, parameters, tools or format. Note, that the model cannot be changed once the chat has started.
