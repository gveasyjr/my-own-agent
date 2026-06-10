import json
import os
import pickle
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']


def get_token_path():
    configured_path = os.getenv('GOOGLE_TOKEN_PICKLE_PATH', '').strip()
    if configured_path:
        return Path(configured_path).expanduser()
    return Path.home() / '.config' / 'my-own-agent' / 'token.pickle'


def main():
    credentials_json = os.getenv('GOOGLE_CREDENTIALS_JSON', '').strip()
    if not credentials_json:
        raise RuntimeError('Set GOOGLE_CREDENTIALS_JSON to a JSON object with your Google OAuth client config.')

    flow = InstalledAppFlow.from_client_config(json.loads(credentials_json), SCOPES)
    creds = flow.run_local_server(port=8080, open_browser=False)

    token_path = get_token_path()
    token_path.parent.mkdir(parents=True, exist_ok=True)
    with token_path.open('wb') as f:
        pickle.dump(creds, f)

    print(f'✅ Authentication successful — token saved to {token_path}')


if __name__ == '__main__':
    main()