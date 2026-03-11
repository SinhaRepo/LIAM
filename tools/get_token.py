import requests
import webbrowser
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import os
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID     = os.getenv("LINKEDIN_CLIENT_ID")
CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")
REDIRECT_URI  = "http://localhost:8000/callback"
SCOPE         = "openid profile w_member_social"

auth_code = None

class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        params = urllib.parse.parse_qs(
            urllib.parse.urlparse(self.path).query
        )
        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"""
                <h2>LIAM Authorization Successful!</h2>
                <p>You can close this tab now.</p>
            """)
        self.server.shutdown_flag = True

    def log_message(self, format, *args):
        pass

def run_server():
    server = HTTPServer(("localhost", 8000), CallbackHandler)
    server.shutdown_flag = False
    while not server.shutdown_flag:
        server.handle_request()

auth_url = (
    f"https://www.linkedin.com/oauth/v2/authorization"
    f"?response_type=code"
    f"&client_id={CLIENT_ID}"
    f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
    f"&scope={urllib.parse.quote(SCOPE)}"
)

print("🚀 LIAM Token Generator")
print("Opening LinkedIn authorization in browser...")
print("Please log in and click Allow.\n")

thread = threading.Thread(target=run_server)
thread.daemon = True
thread.start()

webbrowser.open(auth_url)
thread.join(timeout=120)

if not auth_code:
    print("❌ No code received. Try again.")
    exit()

print("✅ Authorization code received!")
print("Exchanging for access token...\n")

response = requests.post(
    "https://www.linkedin.com/oauth/v2/accessToken",
    data={
        "grant_type":    "authorization_code",
        "code":          auth_code,
        "redirect_uri":  REDIRECT_URI,
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET
    },
    timeout=30
)

data = response.json()

if "access_token" in data:
    token = data["access_token"]

    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            lines = f.readlines()
    else:
        lines = []

    token_line = f"LINKEDIN_ACCESS_TOKEN={token}\n"
    found = False
    for i, line in enumerate(lines):
        if line.startswith("LINKEDIN_ACCESS_TOKEN"):
            lines[i] = token_line
            found = True
            break
            
    if not found:
        lines.append(token_line)

    with open(env_path, "w") as f:
        f.writelines(lines)

    print("✅ Access token saved to .env automatically!")
    print(f"⏰ Expires in: {data.get('expires_in', 'N/A')} seconds (~60 days)")
    print("\n🎉 LIAM is authorized and ready to post!")
else:
    print("❌ Error:", data)
