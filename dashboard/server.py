#!/usr/bin/env python3
"""
Simple HTTP server for the dashboard SPA.
Serves dashboard.html and provides stub API endpoints.
Run: python3 server.py   (from /home/adamsl/letta-code/dashboard/)
Then open: http://localhost:8765/
"""
import json
import os
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Resolve paths relative to this file so the server works from any cwd.
HERE = os.path.dirname(os.path.abspath(__file__))

class DashboardHandler(SimpleHTTPRequestHandler):
    """Serve dashboard HTML and API endpoints."""

    def do_GET(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query = parse_qs(parsed_path.query)

        # API endpoints
        if path == '/api/agents':
            return self.json_response([
                {'id': 'agent-1', 'name': 'Scissari', 'model': 'gpt-5.3-codex'},
                {'id': 'agent-2', 'name': 'Cesare', 'model': 'claude-opus-4.8'},
                {'id': 'agent-3', 'name': 'Jeri', 'model': 'gpt-5.3-codex'},
                {'id': 'agent-4', 'name': 'Mazda', 'model': 'claude-sonnet-4.6'},
                {'id': 'agent-5', 'name': 'Frita', 'model': 'gpt-5.4-mini-plus'},
                {'id': 'agent-6', 'name': 'Hailey', 'model': 'claude-haiku-4.5'},
                {'id': 'agent-7', 'name': 'Claude', 'model': 'claude-opus-4.8'},
            ])

        if path == '/api/thoughts':
            agent_id = query.get('agent', [''])[0]
            return self.json_response([
                {'date': datetime.now().isoformat(), 'text': f'**Loading thoughts** for agent {agent_id}...'},
                {'date': datetime.now().isoformat(), 'text': 'Monitoring system health'},
                {'date': datetime.now().isoformat(), 'text': '**Status**: All systems nominal'},
            ])

        if path == '/api/messages':
            agent_id = query.get('agent', [''])[0]
            return self.json_response([
                {'date': datetime.now().isoformat(), 'type': 'user_message', 'text': 'Hello agent'},
                {'date': datetime.now().isoformat(), 'type': 'assistant_message', 'text': f'Hi! I am {agent_id}.'},
            ])

        if path == '/api/toolcalls':
            agent_id = query.get('agent', [''])[0]
            return self.json_response([
                {'date': datetime.now().isoformat(), 'type': 'tool_call_message', 'text': 'Called bash with: ls -la'},
                {'date': datetime.now().isoformat(), 'type': 'tool_return_message', 'text': 'Output: total 42...'},
            ])

        # Default: serve dashboard HTML
        if path == '/' or path == '':
            self.serve_file(os.path.join(HERE, 'dashboard.html'), 'text/html')
            return

        # Try to serve static files from the dashboard directory
        if path.startswith('/'):
            file_path = os.path.join(HERE, path.lstrip('/'))
            if os.path.isfile(file_path):
                self.serve_file(file_path)
                return

        self.send_error(404)

    def do_POST(self):
        """Handle test message POST."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        if path == '/api/test':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            try:
                data = json.loads(body)
                agent_id = data.get('agent', 'unknown')
                text = data.get('text', '')
                return self.json_response({
                    'replies': [
                        {'type': 'assistant_message', 'text': f'Agent {agent_id} received: "{text}"'},
                        {'type': 'assistant_message', 'text': 'Simulated response from agent.'},
                    ]
                })
            except json.JSONDecodeError:
                return self.error_response('Invalid JSON', 400)

        self.send_error(404)

    def serve_file(self, file_path, content_type=None):
        """Serve a file."""
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            self.send_response(200)
            if content_type is None:
                if file_path.endswith('.html'):
                    content_type = 'text/html'
                elif file_path.endswith('.js'):
                    content_type = 'application/javascript'
                elif file_path.endswith('.css'):
                    content_type = 'text/css'
                else:
                    content_type = 'application/octet-stream'
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404)

    def json_response(self, data):
        """Send a JSON response."""
        response = json.dumps(data, indent=2).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(response))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(response)

    def error_response(self, message, code=400):
        """Send an error response."""
        response = json.dumps({'error': message}).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(response))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, format, *args):
        """Log HTTP requests."""
        print(f"[{self.log_date_time_string()}] {format % args}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8765))
    server = HTTPServer(('0.0.0.0', port), DashboardHandler)
    print(f"Dashboard server running at http://localhost:{port}/")
    print(f"Serving: {os.path.join(HERE, 'dashboard.html')}")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
