from flask import Flask, request, jsonify, render_template_string
from anthropic import AnthropicVertex
import os
import re

app = Flask(__name__)

project_id = os.environ.get("VERTEX_AI_PROJECT_ID")
region = os.environ.get("VERTEX_AI_REGION")
model_name = os.environ.get("MODEL_NAME", "claude-3-5-sonnet@20240620")

client = AnthropicVertex(project_id=project_id, region=region)

# Guardrails system prompt
SYSTEM_PROMPT = """You are an AI assistant specialized in Red Hat technologies and ISO standards.

STRICT RULES:
1. ONLY answer questions about:
   - Red Hat products (RHEL, OpenShift, Ansible, Red Hat OpenShift AI, etc.)
   - ISO standards (ISO 27001, ISO 9001, ISO 20000, etc.)
   - Compliance and certification topics related to the above

2. For ANY other topic, respond with:
   "I can only answer questions about Red Hat technologies and ISO standards. Please ask a question related to these topics."

3. Do not engage with general knowledge, other vendors, or unrelated topics."""

# Simple keyword filter for guardrails
ALLOWED_KEYWORDS = [
    'red hat', 'rhel', 'openshift', 'ansible', 'rhoai', 'fedora',
    'iso 27001', 'iso 9001', 'iso 20000', 'iso', 'compliance',
    'certification', 'security', 'audit', 'standards'
]

def check_guardrails(user_message):
    """Check if message is about allowed topics"""
    message_lower = user_message.lower()
    for keyword in ALLOWED_KEYWORDS:
        if keyword in message_lower:
            return True
    return False

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Claude Playground - Red Hat & ISO Specialist</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #ee0000 0%, #a00000 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 { margin-bottom: 10px; font-size: 28px; }
        .header p { opacity: 0.9; font-size: 14px; }
        .info {
            background: #f8f9fa;
            padding: 20px;
            border-bottom: 1px solid #dee2e6;
        }
        .info-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }
        .info-item {
            background: white;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #ee0000;
        }
        .info-label { font-size: 12px; color: #666; margin-bottom: 5px; }
        .info-value { font-weight: 600; color: #333; }
        .chat-container { padding: 30px; }
        .input-area {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 20px;
        }
        textarea {
            width: 100%;
            min-height: 120px;
            padding: 15px;
            border: 2px solid #dee2e6;
            border-radius: 8px;
            font-size: 16px;
            font-family: inherit;
            resize: vertical;
            transition: border-color 0.3s;
        }
        textarea:focus {
            outline: none;
            border-color: #ee0000;
        }
        button {
            background: linear-gradient(135deg, #ee0000 0%, #a00000 100%);
            color: white;
            border: none;
            padding: 15px 40px;
            font-size: 16px;
            font-weight: 600;
            border-radius: 8px;
            cursor: pointer;
            margin-top: 15px;
            transition: transform 0.2s, box-shadow 0.3s;
        }
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(238, 0, 0, 0.3);
        }
        button:active { transform: translateY(0); }
        button:disabled {
            background: #ccc;
            cursor: not-allowed;
            transform: none;
        }
        .response-area {
            background: white;
            border: 2px solid #dee2e6;
            border-radius: 12px;
            padding: 25px;
            min-height: 200px;
            line-height: 1.6;
        }
        .response-area.loading {
            display: flex;
            align-items: center;
            justify-content: center;
            color: #666;
        }
        .response-area.error {
            background: #fff5f5;
            border-color: #feb2b2;
            color: #c53030;
        }
        .response-area.success {
            background: #f0fdf4;
            border-color: #86efac;
        }
        .spinner {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #ee0000;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin-right: 15px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .guardrails-notice {
            background: #fff3cd;
            border: 1px solid #ffc107;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
            font-size: 14px;
            color: #856404;
        }
        .guardrails-notice strong { color: #ee0000; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Claude Playground</h1>
            <p>Red Hat Technologies & ISO Standards Specialist</p>
        </div>

        <div class="info">
            <div class="info-grid">
                <div class="info-item">
                    <div class="info-label">Project</div>
                    <div class="info-value">{{ project_id }}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Region</div>
                    <div class="info-value">{{ region }}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Model</div>
                    <div class="info-value">Claude 3.5 Sonnet</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Guardrails</div>
                    <div class="info-value">✅ Enabled</div>
                </div>
            </div>
        </div>

        <div class="chat-container">
            <div class="guardrails-notice">
                <strong>⚠️ Content Policy:</strong> This assistant only answers questions about <strong>Red Hat technologies</strong> and <strong>ISO standards</strong>. All other topics will be rejected.
            </div>

            <div class="input-area">
                <textarea id="prompt" placeholder="Ask about Red Hat products or ISO standards...">What is Red Hat OpenShift AI and how does it help with ISO 27001 compliance?</textarea>
                <button onclick="sendMessage()" id="sendBtn">Send Message</button>
            </div>

            <div id="response" class="response-area">
                Response will appear here...
            </div>
        </div>
    </div>

    <script>
    async function sendMessage() {
        const prompt = document.getElementById('prompt').value;
        const responseDiv = document.getElementById('response');
        const sendBtn = document.getElementById('sendBtn');

        if (!prompt.trim()) return;

        responseDiv.className = 'response-area loading';
        responseDiv.innerHTML = '<div class="spinner"></div><span>Thinking...</span>';
        sendBtn.disabled = true;

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: prompt})
            });

            const data = await response.json();

            if (data.error) {
                responseDiv.className = 'response-area error';
                responseDiv.innerHTML = '<strong>Error:</strong> ' + data.error;
            } else if (data.blocked) {
                responseDiv.className = 'response-area error';
                responseDiv.innerHTML = '<strong>🚫 Blocked by Guardrails:</strong><br><br>' + data.response;
            } else {
                responseDiv.className = 'response-area success';
                responseDiv.innerHTML = data.response.replace(/\\n/g, '<br>');
            }
        } catch (error) {
            responseDiv.className = 'response-area error';
            responseDiv.innerHTML = '<strong>Error:</strong> ' + error.message;
        } finally {
            sendBtn.disabled = false;
        }
    }

    document.getElementById('prompt').addEventListener('keydown', function(e) {
        if (e.ctrlKey && e.key === 'Enter') {
            sendMessage();
        }
    });
    </script>
</body>
</html>
'''

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE,
                                 project_id=project_id,
                                 region=region)

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get('message', '')

        # Apply guardrails
        if not check_guardrails(user_message):
            return jsonify({
                'blocked': True,
                'response': 'I can only answer questions about Red Hat technologies and ISO standards. Please ask a question related to these topics.'
            })

        # Call Claude with system prompt
        message = client.messages.create(
            model=model_name,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}]
        )

        return jsonify({
            'response': message.content[0].text,
            'blocked': False
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'model': model_name,
        'project': project_id,
        'guardrails': 'enabled'
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
