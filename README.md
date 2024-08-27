# Ollama to LM Studio API Proxy/Converter
A simple proxy that transforms requests from Ollama to LM Studio, so that you can use applications that only support Ollama.

I mainly created this for use with GitButler, but I could also see it being useful for other purposes.

## API Endpoints

Here is a list of the endpoints and where they point to. In a table below.
The first column is the ollama endpoint, and the second column is the LM Studio endpoint that it is forwarded to.

| Ollama Endpoint      | LM Studio Endpoint   |
|----------------------|----------------------|
| /api/chat            | /v1/chat/completions |

## Setup 

You need to have a working Ollama installation and LM Studio. Please look up their getting started guides initially if you haven't got those already.

For me, GitButler did not like using a different port number, so I had to change Ollama's default port to `11435` by using the environment variable `OLLAMA_HOST=127.0.0.1:11435`.

However, for broad compatibility, this is probably the recommended method since a lot of applications might not let you configure the port, but Ollama does allow you to change it.

On Linux I had to do the following:

1. Open the file `/etc/systemd/system/ollama.service` in your favourite editor. 
   1. You might have to edit as root, e.g. `nano /etc/systemd/system/ollama.service` 
2. Add an extra line after `Environment="PATH=..."` with `Environment="OLLAMA_HOST=127.0.0.1:11435"`.
   1. So you should have something like:
   ```
   [Unit]
   Description=Ollama Service
   After=network-online.target

   [Service]
   ExecStart=/usr/local/bin/ollama serve
   User=ollama
   Group=ollama
   Restart=always
   RestartSec=3
   Environment="PATH=..."
   Environment="OLLAMA_HOST=127.0.0.1:11435"
   
   [Install]
   WantedBy=default.target
   ```

If you want to keep Ollama's default port, you need to change the line `app.run(host='127.0.0.1', port=11434)` and replace the port number `11434` with whatever you have configured in your client making requests to Ollama.

## Usage

Once the script is running, you can use any Ollama-compatible application by pointing it to `http://localhost:11434` (or the appropriate host and port if you've modified the configuration).

## Issues

Really the only issue at the moment are:

- LM Studio returns usage as tokens, but Ollama returns durations.
  - This means mapping them needs to be calculated somehow.
  - For now, I have these as placeholders set to 0, so that there are no issues with software expecting them.
- This is very rough code that I threw together quickly. Needs more polish!

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request or raise any Issues you have.

## License

This project is licensed under the [MIT License](LICENSE).

## Acknowledgements

- [Ollama](https://github.com/ollama/ollama)
- [LM Studio](https://lmstudio.ai/)
- [LM Studio CLI](https://github.com/lmstudio-ai/lms)
- [GitButler](https://github.com/gitbutlerapp/gitbutler)