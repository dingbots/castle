import os
import json

import awsgi
from flask import Flask, request
import urllib3
import github_webhook
from github import Github
from werkzeug.local import LocalProxy


CLIENT_ID = os.environ.get('github-client-id')
CLIENT_SECRET = os.environ.get('github-client-secret')


def get_global_github():
    return Github(client_id=CLIENT_ID, client_secret=CLIENT_SECRET)

def get_github(token):
    return Github(token)

ghclient = LocalProxy(get_global_github)


app = Flask(__name__)
webhook = github_webhook.Webhook(
    app,
    endpoint='/postreceive',
    secret=os.environ.get('github-webhook-secret'),
)

http = urllib3.PoolManager()


@app.route('/')
def hello_world():
    return "Hello, World!"


# This is part of the OAuth flow for acting as a User
@app.route('/authorization')
def authorization_callback():
    session_code = request.args.get('code')
    # This doesn't seem to be part of PyGithub
    resp = http.request(
        'POST',
        'https://github.com/login/oauth/access_token',
        fields={
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'code': session_code,
        },
    )

    respdata = json.loads(resp.data.decode('utf-8'))
    access_token = respdata['access_token']
    github = get_github(access_token)

    userdata = github.get_user()
    # TODO: Save access_token with userdata


@webhook.hook('ping')
def ping(payload):
    return "pong"


def main(event, context):
    rv = awsgi.response(app, event, context, base64_content_types={})
    return rv
