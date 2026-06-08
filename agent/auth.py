from google_auth_oauthlib.flow import InstalledAppFlow
import pickle

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

flow = InstalledAppFlow.from_client_secrets_file(
    '/Users/geoffreyveasy/MYSERVER/agent/credentials.json',
    SCOPES
)

creds = flow.run_local_server(port=8080, open_browser=False)

with open('/Users/geoffreyveasy/MYSERVER/agent/token.pickle', 'wb') as f:
    pickle.dump(creds, f)

print("✅ Authentication successful — token.pickle saved")