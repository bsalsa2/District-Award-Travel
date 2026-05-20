from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import json
import os
import logging

class AdminHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            with open('index.html', 'r') as f:
                self.wfile.write(f.read().encode())
        elif parsed_path.path == '/submissions':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            submissions = []
            for file in os.listdir('submissions'):
                with open(f'submissions/{file}', 'r') as f:
                    submissions.append(json.load(f))
            self.wfile.write(json.dumps(submissions).encode())
        elif parsed_path.path == '/revenue':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            revenue = 0
            for file in os.listdir('submissions'):
                with open(f'submissions/{file}', 'r') as f:
                    submission = json.load(f)
                    revenue += submission['amount']
            self.wfile.write(json.dumps({'revenue': revenue}).encode())
        elif parsed_path.path == '/pipeline':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            pipeline_status = 'active'
            self.wfile.write(json.dumps({'pipeline_status': pipeline_status}).encode())
        elif parsed_path.path == '/logs':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            logs = []
            for file in os.listdir('logs'):
                with open(f'logs/{file}', 'r') as f:
                    logs.append(f.read())
            self.wfile.write(json.dumps(logs).encode())
        elif parsed_path.path == '/bonus':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            bonus = 'active'
            self.wfile.write(json.dumps({'bonus': bonus}).encode())

    def do_POST(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path == '/login':
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            data = parse_qs(body.decode())
            if data['password'][0] == 'secret':
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                with open('index.html', 'r') as f:
                    self.wfile.write(f.read().encode())
            else:
                self.send_response(401)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b'Invalid password')

def run_server():
    server_address = ('', 8080)
    httpd = HTTPServer(server_address, AdminHandler)
    print('Starting admin server on port 8080...')
    httpd.serve_forever()

if __name__ == '__main__':
    run_server()
