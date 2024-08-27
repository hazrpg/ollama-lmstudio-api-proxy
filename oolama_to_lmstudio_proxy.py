from flask import Flask, request, jsonify
import requests
from datetime import datetime
import json

app = Flask(__name__)

# Configure OLP (Ollama to LM Studio Proxy) API endpoint.
OLP_HOST = "127.0.0.1"
OLP_PORT = 11434 # Change this port to whatever your expected caller application sends requests to, by default its Ollama's port is 11434

# OLP Settings
WORKAROUND_FOR_GITBUTLER = True
DEBUGGING = True

# Configure LM Studio's API endpoint.
LM_STUDIO_PORT = 1234
LM_STUDIO_API_URL = f"http://localhost:{LM_STUDIO_PORT}/v1/chat/completions"

# Configure Ollama's API endpoint
# Commented out because it was used for debugging.
# OLLAMA_PORT = 11435 # Default for Ollama is 11434
# OLLAMA_API_URL = f"http://localhost:{OLLAMA_PORT}/api/chat"

@app.route('/api/chat', methods=['POST'])
def proxy_to_lm_studio():
    """
    This function acts as a proxy between the original caller application and LM Studio's API.
    It receives a JSON request, forwards it to LM Studio, and transforms the response
    to match the expected format of the original caller (in this case Ollama style response).

    Parameters:
        None (uses Flask's request object)

    Returns:
        A JSON response with the transformed data from LM Studio, along with the
        status code from LM Studio's API response.
    """

    # Extract the request data (assuming it's JSON)
    request_data = request.get_json()

    # Print the incoming request data for debugging
    if DEBUGGING:
        print('INCOMING REQUEST:')
        print(request_data)
        print('')

    # Forward the request to LM Studio (note that LM Studio does not need the data transformed)
    lm_response = requests.post(LM_STUDIO_API_URL, json=request_data)
    lm_data = lm_response.json()

    # Print the LM Studio response for debugging
    if DEBUGGING:
        print('LM STUDIO RESPONSE:')
        print(lm_data)
        print('')

    # Forward the request to Ollama
    # o_response = requests.post(OLLAMA_API_URL, json=request_data)
    # o_data = o_response.json()

    # Print the Ollama response for debugging
    # if DEBUGGING:
    #     print('OLLAMA RESPONSE:')
    #     print(o_data)
    #     print('')

    # Transform the response from LM Studio to match what Ollama-clients expects
    message = ""
    done_response = "unknown"
    if lm_data.get("choices"):
        # Extract the message from the LM Studio response
        message = lm_data["choices"][0]["message"]

        # Workaround for GitButler, it wants the AI response message to be a JSON object for some reason.
        if WORKAROUND_FOR_GITBUTLER:
            # Convert the message to a JSON object
            message_json = {
                "result": message["content"]
            }

            # Replace the message with the JSON object
            message["content"] = json.dumps(message_json)

        # Extract the done reason from the LM Studio response
        done_response = lm_data["choices"][0]["finish_reason"]

    # Transform the response from LM Studio to match what Ollama expects
    transformed_response = {
        "model": request_data.get("model", "llama3"), # Most applications might require it to be llama3 back.
        "created_at": datetime.utcfromtimestamp(lm_data.get("created")).isoformat() + "Z",
        "message": message,
        "done": True,
        "done_reason": done_response,
        "total_duration": 0,  # Placeholder, as LM Studio doesn't provide this directly
        "load_duration": 0,   # Placeholder, as LM Studio doesn't provide this directly
        "prompt_eval_count": 0,  # Placeholder, as LM Studio doesn't provide this directly
        "prompt_eval_duration": 0,  # Placeholder, as LM Studio doesn't provide this directly
        "eval_count": 0,  # Placeholder, as LM Studio doesn't provide this directly
        "eval_duration": 0  # Placeholder, as LM Studio doesn't provide this directly
    }

    # Print the transformed response for debugging
    if DEBUGGING:
        print('SENDING THIS BACK INSTEAD:')
        print(transformed_response)
        print('')

    # Return the transformed response to the original caller
    return jsonify(transformed_response), lm_response.status_code # return lm studio

    # Uncomment this if you want to return Ollama's response instead
    #return o_data, 200 # return ollama

if __name__ == '__main__':
    app.run(host=OLP_HOST, port=OLP_PORT)
