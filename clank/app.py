import os
import sys

from flask import Flask
import github_webhook
from gqlmod_github.app import GithubApp
from werkzeug.local import LocalProxy

import ghstatus


CLIENT_ID = os.environ.get('github_client_id')
CLIENT_SECRET = os.environ.get('github_client_secret')

APP_ID = os.environ.get('github_application_id')
APP_PRIVATE_KEY = os.environ.get('github_private_key').encode('ascii')


@LocalProxy
def ghapp():
    return GithubApp(APP_ID, APP_PRIVATE_KEY)


app = Flask(__name__)
webhook = github_webhook.Webhook(
    app,
    endpoint='/postreceive',
    secret=os.environ.get('github_webhook_secret'),
)


class OutputManager:
    """
    Handles the output buffer and sending things to GitHub
    """
    def __init__(self, repo_id, sha):
        self.repo_id = repo_id
        self.git_sha = sha
        self.annotations = []
        self.output = ""
        self.total_annotations = 0
        self.run_id = None

    def write(self, s):
        self.output += s
        sys.stdout.write(s)
        return len(s)

    def annotate(self, fname, line, col, msg):
        self.annotations.append({
            'path': fname,
            'location': {
                'startLine': line,
                'endLine': line,
                'startColumn': col,
                'endColumn': col,
            },
            'annotationLevel': 'FAILURE',
            'message': msg,
        })
        self.total_annotations += 1
        if len(self.annotations) > 40:
            self.flush()

    def __enter__(self):
        res = ghstatus.start_check_run(repo=self.repo_id, sha=self.git_sha)
        assert not res.errors
        self.run_id = res.data['createCheckRun']['checkRun']['id']
        # FIXME: Handle the case if we don't have permissions
        return self

    def __exit__(self, *_):
        # TODO: L10n
        if self.total_annotations == 0:
            summary = "No problems found"
        elif self.total_annotations == 1:
            summary = "1 problem found"
        else:
            summary = f"{self.total_annotations} problems found"
        print(summary, file=self)
        self.flush()
        ghstatus.complete_check_run(
            repo=self.repo_id,
            checkrun=self.run_id,
            summary=summary,
            state='FAILURE' if self.total_annotations else 'SUCCESS'
        )


@app.route('/')
def root():
    """
    Basic status call
    """
    return "Service is running"


# This is part of the OAuth flow for acting as a User
@app.route('/authorization')
def authorization_callback():
    return 'OAuth is not used by this service', 418


@webhook.hook('push')
def push(payload):
    with ghapp.for_repo(
        payload['repository']['owner']['name'], payload['repository']['name'],
        repo_id=payload['repository']['id']
    ):
        with OutputManager(
            payload['repository']['node_id'], payload['head']
        ) as output:
            print("Hello, World!", file=output)
