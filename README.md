# Ollama to LM Studio API Proxy/Converter

A simple proxy that transforms API requests intended for Ollama into the format expected by LM Studio, allowing you to use LM Studio with applications that only support Ollama's API.

This project was primarily created for use with GitButler, which supports Ollama, but it can be useful for other applications as well.

## API Endpoints

Here is a list of the Ollama endpoints that are proxied and the corresponding LM Studio endpoints they are forwarded to:

| Ollama Endpoint | LM Studio Endpoint     | Notes                               |
| :-------------- | :--------------------- | :---------------------------------- |
| `/api/chat`     | `/v1/chat/completions` | Handles both streaming and non-streaming requests. Transforms response format. |
| `/api/tags`     | `/v1/models`           | Transforms response format.           |

## Setup

To use this proxy, you need:

1.  **LM Studio:** Have LM Studio installed and running, with the models you wish to use loaded.
2.  **This Proxy Script:** Run this Python script.
3.  **Client Configuration:** Configure your Ollama-compatible application (e.g., GitButler) to connect to this proxy's address and port instead of a running Ollama instance.

### Configuration

You can configure the proxy's behavior by editing the following variables at the top of the `ollama_lm_studio_proxy.py` script:

*   `OLP_HOST`: The IP address the proxy server will listen on (e.g., `"127.0.0.1"` for localhost).
*   `OLP_PORT`: The port the proxy server will listen on. This is the port your client application should connect to (default is `11434`, Ollama's default).
*   `LM_STUDIO_PORT`: The port LM Studio's API is running on (default is `11234`). The `LM_STUDIO_BASE_URL` and `LM_STUDIO_CHAT_URL`/`LM_STUDIO_MODELS_URL` are derived from this.
*   `WORKAROUND_FOR_GITBUTLER`: A boolean flag. Setting this to `True` applies a specific response transformation needed for GitButler's *non-streaming* chat response parsing (it wraps the content in a `{"result": "..."}` JSON string). **Note:** This workaround is ignored for streaming requests. For most other clients, it should likely be `False`.
*   `DEBUGGING`: A boolean flag. Set to `True` to print detailed request/response information to the console for debugging purposes.

### Running on Ollama's Default Port (11434)

If your client application *must* connect to port `11434` and you *also* have Ollama installed and potentially running on the same machine, you might need to change Ollama's default port to free up `11434` for the proxy. A common way to do this is by setting the `OLLAMA_HOST` environment variable for the Ollama service.

For example, on Linux systems using `systemd`, you can edit the Ollama service file (`/etc/systemd/system/ollama.service`) and add the line:

```
Environment="OLLAMA_HOST=127.0.0.1:11435"
```

After modifying the service file, reload the systemd manager configuration (`sudo systemctl daemon-reload`) and restart the Ollama service (`sudo systemctl restart ollama`). This will make Ollama listen on port `11435`, allowing you to run the proxy on `11434`.

## Usage

1.  Ensure LM Studio is running and serving models on its configured port (default 11234).
2.  Run the Python script: `python ollama_lm_studio_proxy.py`
3.  Configure your Ollama-compatible application to connect to the proxy's host and port (e.g., `http://127.0.0.1:11434`).

The proxy will now intercept calls to `/api/chat` and `/api/tags`, forward them to LM Studio, and convert the responses back to the Ollama format expected by your client.

## Issues and Limitations

*   **Duration Metrics:** LM Studio provides token counts (prompt, completion) in its `usage` data, which are mapped to `prompt_eval_count` and `eval_count` respectively in the Ollama response. However, Ollama also provides detailed timing/duration metrics (`total_duration`, `load_duration`, etc.), which LM Studio does not expose in the same way. These duration fields are currently hardcoded to `0` in the proxy response to maintain compatibility.
*   **GitButler Workaround:** The `WORKAROUND_FOR_GITBUTLER` setting is a specific transformation applied to *non-streaming* responses based on observed behavior with GitButler. It may not be needed for other clients and is ignored for streaming requests.
*   **Endpoint Coverage:** Currently, only `/api/chat` and `/api/tags` are implemented. Other Ollama endpoints (like `/api/generate`, `/api/embeddings`, etc.) are not yet supported. Requests to unimplemented endpoints will likely result in a 404 error.
*   **Robustness & Features:** This is a relatively simple proxy. More advanced features like full error mapping, better logging, support for more Ollama request parameters, etc., could be added.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request or raise any Issues you have.

## License

This project is licensed under the [MIT License](LICENSE).

## Acknowledgements

*   [Ollama](https://github.com/ollama/ollama)
*   [LM Studio](https://lmstudio.ai/)
*   [LM Studio CLI](https://github.com/lmstudio-ai/lms)
*   [GitButler](https://github.com/gitbutlerapp/gitbutler)
