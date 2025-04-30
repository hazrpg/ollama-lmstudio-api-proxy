from flask import Flask, request, jsonify, Response, stream_with_context # Added Response, stream_with_context
import requests
from datetime import datetime, timezone
import json
from flask_cors import CORS

app = Flask(__name__)
CORS(app) # Enable CORS

# Configure OLP (Ollama to LM Studio Proxy) API endpoint.
OLP_HOST = "127.0.0.1"
OLP_PORT = 11434 # Change this port to whatever your expected caller application sends requests to, by default its Ollama's port is 11434

# OLP Settings
WORKAROUND_FOR_GITBUTLER = False # NOTE: This workaround is ignored during streaming
DEBUGGING = True
LM_STUDIO_PORT = 11234
LM_STUDIO_BASE_URL = f"http://localhost:{LM_STUDIO_PORT}/v1"
LM_STUDIO_CHAT_URL = f"{LM_STUDIO_BASE_URL}/chat/completions"
LM_STUDIO_MODELS_URL = f"{LM_STUDIO_BASE_URL}/models"
# --- End Configuration ---

# Helper function to create Ollama-style stream chunks
def format_ollama_stream_chunk(model_name, content_delta, created_at_iso, done=False, done_reason=None, final_stats=None):
    """Formats a chunk for Ollama streaming response."""
    chunk = {
        "model": model_name,
        "created_at": created_at_iso,
        "message": {
            "role": "assistant",
            "content": content_delta # Send only the delta
        },
        "done": done,
    }
    if done:
        # For the final chunk, add reason and potentially stats
        chunk["done_reason"] = done_reason if done_reason else "stop" # Default to stop if None
        if final_stats:
             chunk.update(final_stats) # Add stats if provided
        # Ensure message is present even if empty content in final chunk
        if "message" not in chunk or not chunk["message"]:
             chunk["message"] = {"role": "assistant", "content": ""}

    # Important: Each JSON object must be followed by a newline for ndjson
    return json.dumps(chunk) + '\n'

@app.route('/api/chat', methods=['POST'])
def proxy_to_lm_studio_chat():
    """
    Proxies '/api/chat' requests to LM Studio.
    Handles both streaming and non-streaming responses based on request payload.
    """
    try:
        request_data = request.get_json()
        if not request_data:
            return jsonify({"error": "Invalid JSON payload"}), 400
    except Exception as e:
        if DEBUGGING: print(f"Error parsing request JSON: {e}")
        return jsonify({"error": f"Failed to parse request JSON: {e}"}), 400

    is_streaming = request_data.get("stream", True)
    model_name = request_data.get("model", "unknown_model") # Get model name early

    if DEBUGGING:
        print(f'INCOMING /api/chat REQUEST (Streaming: {is_streaming}):')
        print(json.dumps(request_data, indent=2))
        print('')

    # --- Streaming Logic ---
    if is_streaming:
        # Make sure stream is True in the forwarded request
        request_data["stream"] = True
        # GitButler workaround is incompatible with streaming
        if WORKAROUND_FOR_GITBUTLER and DEBUGGING:
            print("Note: WORKAROUND_FOR_GITBUTLER is ignored for streaming requests.")

        def event_stream():
            created_at_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            last_chunk_data = {} # To store final stats if needed
            finish_reason = None

            try:
                # Use stream=True with requests
                with requests.post(LM_STUDIO_CHAT_URL, json=request_data, stream=True, timeout=300) as lm_response:
                    lm_response.raise_for_status() # Check for initial HTTP errors

                    if DEBUGGING: print('LM STUDIO STREAMING RESPONSE STARTED')

                    for line in lm_response.iter_lines():
                        if line:
                            decoded_line = line.decode('utf-8')

                            # LM Studio/OpenAI often send SSE format: "data: {...}"
                            if decoded_line.startswith('data: '):
                                json_str = decoded_line[len('data: '):].strip()
                            else:
                                # Assume it might just be JSON directly in some cases
                                json_str = decoded_line

                            # Check for final SSE message '[DONE]'
                            if json_str == '[DONE]':
                                if DEBUGGING: print("LM Studio stream finished with [DONE]")
                                break # Stop processing lines

                            if not json_str: continue # Skip empty lines after stripping 'data: '

                            try:
                                chunk_data = json.loads(json_str)
                                if DEBUGGING:
                                    print('LM STUDIO CHUNK RECEIVED:')
                                    print(json.dumps(chunk_data, indent=2))

                                # --- Transform LM Studio Chunk to Ollama Chunk ---
                                content_delta = ""
                                choices = chunk_data.get("choices", [])
                                if choices and isinstance(choices, list) and len(choices) > 0:
                                    delta = choices[0].get("delta", {})
                                    content_delta = delta.get("content", "")
                                    # Check for finish reason in the chunk
                                    if choices[0].get("finish_reason"):
                                        finish_reason = choices[0].get("finish_reason")
                                        if DEBUGGING: print(f"Finish reason detected in chunk: {finish_reason}")

                                # Store potential final usage stats (might appear in last data chunk before or instead of [DONE])
                                usage = chunk_data.get("usage")
                                if usage:
                                    last_chunk_data["total_duration"] = 0 # Placeholder
                                    last_chunk_data["load_duration"] = 0 # Placeholder
                                    last_chunk_data["prompt_eval_count"] = usage.get("prompt_tokens", 0)
                                    last_chunk_data["prompt_eval_duration"] = 0 # Placeholder
                                    last_chunk_data["eval_count"] = usage.get("completion_tokens", 0)
                                    last_chunk_data["eval_duration"] = 0 # Placeholder
                                    if DEBUGGING: print(f"Usage stats received in chunk: {usage}")


                                # Yield intermediate chunk if there's content
                                if content_delta:
                                     ollama_chunk = format_ollama_stream_chunk(
                                         model_name=model_name,
                                         content_delta=content_delta,
                                         created_at_iso=created_at_iso,
                                         done=False
                                     )
                                     if DEBUGGING:
                                         print('YIELDING OLLAMA CHUNK:')
                                         print(ollama_chunk.strip())
                                         print("-" * 20)
                                     yield ollama_chunk.encode('utf-8') # Yield bytes

                            except json.JSONDecodeError:
                                if DEBUGGING: print(f"Skipping non-JSON line: {json_str}")
                                continue # Ignore lines that aren't valid JSON data chunks
                            except Exception as e_transform:
                                if DEBUGGING: print(f"Error transforming chunk: {e_transform}\nChunk: {json_str}")
                                # Decide if you want to yield an error chunk or just continue/break
                                # yield format_ollama_stream_chunk(model_name, f"Error: {e_transform}", created_at_iso, done=True, done_reason="error").encode('utf-8')
                                # break # Stop streaming on error

                    # After the loop finishes (or breaks on [DONE]/error) - yield the final chunk
                    final_ollama_chunk = format_ollama_stream_chunk(
                        model_name=model_name,
                        content_delta="", # No more content in the final meta chunk
                        created_at_iso=created_at_iso,
                        done=True,
                        done_reason=finish_reason, # Use the detected reason
                        final_stats=last_chunk_data # Include any collected stats
                    )
                    if DEBUGGING:
                        print('YIELDING FINAL OLLAMA CHUNK:')
                        print(final_ollama_chunk.strip())
                        print("=" * 20)
                    yield final_ollama_chunk.encode('utf-8')

            except requests.exceptions.RequestException as e:
                error_message = f"Error connecting to LM Studio stream: {e}"
                if DEBUGGING: print(error_message)
                # Yield a final error chunk to the client
                yield format_ollama_stream_chunk(model_name, error_message, datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), done=True, done_reason="error").encode('utf-8')
            except Exception as e:
                error_message = f"Unexpected error during streaming: {e}"
                if DEBUGGING: print(error_message)
                # Yield a final error chunk to the client
                yield format_ollama_stream_chunk(model_name, error_message, datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), done=True, done_reason="error").encode('utf-8')
            finally:
                 if DEBUGGING: print('LM STUDIO STREAMING RESPONSE FINISHED')


        # Return a Streaming Response using the generator
        # Use stream_with_context to ensure generator has access to app/request context if needed
        return Response(stream_with_context(event_stream()), mimetype='application/x-ndjson')

    # --- Non-Streaming Logic (Original code slightly adapted) ---
    else:
        try:
            # Make the normal non-streaming request
            lm_response = requests.post(LM_STUDIO_CHAT_URL, json=request_data, timeout=300)
            lm_response.raise_for_status()
            lm_data = lm_response.json()

            if DEBUGGING:
                print('LM STUDIO NON-STREAMING RESPONSE:')
                print(json.dumps(lm_data, indent=2))
                print('')

        except requests.exceptions.RequestException as e:
            if DEBUGGING: print(f"Error connecting to LM Studio chat endpoint: {e}")
            return jsonify({"error": f"Failed to connect to LM Studio chat endpoint: {e}"}), 502
        except json.JSONDecodeError as e:
             if DEBUGGING: print(f"Error decoding LM Studio chat JSON response: {e}")
             return jsonify({"error": f"Invalid JSON response from LM Studio chat endpoint: {e}"}), 502
        except Exception as e:
            if DEBUGGING: print(f"Unexpected error during LM Studio chat request: {e}")
            return jsonify({"error": f"Unexpected error processing LM Studio chat request: {e}"}), 500

        # Transform the *single* response (Mostly same as before, ensure WORKAROUND applies only here if needed)
        message = {}
        done_response = "unknown"
        prompt_tokens = completion_tokens = 0
        try:
            if lm_data.get("choices") and isinstance(lm_data["choices"], list) and len(lm_data["choices"]) > 0:
                choice = lm_data["choices"][0]
                message = choice.get("message", {})
                done_response = choice.get("finish_reason", "unknown")

                # Apply workaround ONLY if not streaming and flag is True
                if WORKAROUND_FOR_GITBUTLER and message and "content" in message:
                    message_json = {"result": message["content"]}
                    message["content"] = json.dumps(message_json) # Double encoding

            usage = lm_data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")

        except (KeyError, IndexError, TypeError) as e:
            if DEBUGGING: print(f"Error parsing LM Studio response structure: {e}")
            message = {"role": "assistant", "content": "Error processing LM Studio response."}
            done_response = "error"

        try:
            created_timestamp = lm_data.get("created")
            created_at_iso = datetime.fromtimestamp(created_timestamp, timezone.utc).isoformat().replace("+00:00", "Z") if created_timestamp else datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        except Exception:
             created_at_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        transformed_response = {
            "model": model_name,
            "created_at": created_at_iso,
            "message": message, # Contains full message (potentially double-encoded if workaround active)
            "done": True, # Non-streaming is always done=True in the final response
            "done_reason": done_response,
            "total_duration": 0,
            "load_duration": 0,
            "prompt_eval_count": prompt_tokens if prompt_tokens is not None else 0,
            "prompt_eval_duration": 0,
            "eval_count": completion_tokens if completion_tokens is not None else 0,
            "eval_duration": 0
        }

        if DEBUGGING:
            print('SENDING THIS NON-STREAMING BACK INSTEAD:')
            print(json.dumps(transformed_response, indent=2))
            print('')

        return jsonify(transformed_response), lm_response.status_code

# --- /api/tags endpoint remains the same ---
@app.route('/api/tags', methods=['GET'])
def get_tags():
    """
    Proxies '/api/tags' requests to LM Studio's models endpoint
    and transforms the response to Ollama format.
    """
    if DEBUGGING:
        print('INCOMING /api/tags REQUEST')
        print('')
    try:
        lm_response = requests.get(LM_STUDIO_MODELS_URL, timeout=60)
        lm_response.raise_for_status()
        lm_data = lm_response.json()
        if DEBUGGING:
            print('LM STUDIO MODELS RESPONSE:')
            print(json.dumps(lm_data, indent=2))
            print('')
    except requests.exceptions.RequestException as e:
        if DEBUGGING: print(f"Error connecting to LM Studio models endpoint: {e}")
        return jsonify({"error": f"Failed to connect to LM Studio models endpoint: {e}"}), 502
    except json.JSONDecodeError as e:
         if DEBUGGING: print(f"Error decoding LM Studio models JSON response: {e}")
         return jsonify({"error": f"Invalid JSON response from LM Studio models endpoint: {e}"}), 502
    except Exception as e:
        if DEBUGGING: print(f"Unexpected error during LM Studio models request: {e}")
        return jsonify({"error": f"Unexpected error processing LM Studio models request: {e}"}), 500

    # Transform LM Studio models to Ollama tags format
    ollama_models = []
    if lm_data and isinstance(lm_data.get('data'), list):
        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        for model_info in lm_data['data']:
            model_id = model_info.get('id')
            if model_id:
                family = "unknown"
                if '/' in model_id:
                     parts = model_id.split('/')
                     if len(parts) > 1: family = parts[1]
                elif '-' in model_id:
                     family = model_id.split('-')[0]
                ollama_model = {
                    "name": f"{model_id}:latest", "model": f"{model_id}:latest",
                    "modified_at": now_iso, "size": 0, "digest": "",
                    "details": { "parent_model": "", "format": "gguf", "family": family,
                                 "families": [family] if family != "unknown" else None,
                                 "parameter_size": "unknown", "quantization_level": "unknown" }
                }
                if ollama_model["details"]["families"] == ["unknown"]:
                     ollama_model["details"]["families"] = None
                ollama_models.append(ollama_model)
    transformed_response = {"models": ollama_models}

    if DEBUGGING:
        print('SENDING THIS /api/tags BACK INSTEAD:')
        print(json.dumps(transformed_response, indent=2))
        print('')
    return jsonify(transformed_response), 200

if __name__ == '__main__':
    # Use 0.0.0.0 if your client is on a different machine than the proxy
    # app.run(host='0.0.0.0', port=OLP_PORT)
    app.run(host=OLP_HOST, port=OLP_PORT)
