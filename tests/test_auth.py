import pytest
import requests
from unittest.mock import Mock, patch

from micado.launcher.openstack import auth

AUTH_CONSTRUCTOR_CALLS = [
    (
        auth.PasswordAuthenticator,
        {
            "username": "user",
            "password": "pass",
        },
    ),
    (
        auth.AppCredAuthenticator,
        {
            "application_credential_id": "aci",
            "application_credential_secret": "acs",
        },
    ),
    (
        auth.OidcAuthenticator,
        {
            "identity_provider": "ip",
            "access_token": "at",
        },
    ),
]


def test_abstract_authenticator():
    with pytest.raises(NotImplementedError):
        auth.Authenticator().authenticate()


@pytest.mark.parametrize("authenticator,args", AUTH_CONSTRUCTOR_CALLS)
def test_concrete_auth_correct_args(authenticator, args):
    authenticator(**args)


@pytest.mark.parametrize("authenticator,args", AUTH_CONSTRUCTOR_CALLS)
def test_password_auth_missing_args(authenticator, args):
    args.pop(list(args.keys())[0])
    with pytest.raises(TypeError):
        authenticator(**args)


@pytest.mark.parametrize("authenticator,args", AUTH_CONSTRUCTOR_CALLS)
def test_password_auth_too_many_args(authenticator, args):
    args["extra"] = "extra"
    with pytest.raises(TypeError):
        authenticator(**args)

def test_oidc_calls_openid_refresh_with_dict(monkeypatch):
    mocked_fn = Mock()
    monkeypatch.setattr(auth, "refresh_openid_token", mocked_fn)
    auth.OidcAuthenticator(access_token={}, identity_provider="")
    assert(mocked_fn.called)


@pytest.fixture
def requests_patch(monkeypatch, request):
    def patched_post(*args, **kwargs):
        mocked_response = Mock()
        mocked_response.json = lambda: {request.param: kwargs}
        return mocked_response

    monkeypatch.setattr(requests, "post", patched_post)


@pytest.mark.parametrize("requests_patch", ["access_token"], indirect=True)
def test_openid_token_refresh_request_body(requests_patch):
    url = "http://test.com"
    client_id, client_secret, token = "cli_id", "cli_sec", "ref_tok"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": token,
        "scope": "openid email profile",
    }
    response = auth.refresh_openid_token(
        url=url,
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=token,
    )
    assert response["url"] == url
    assert response["auth"] == (client_id, client_secret)
    assert response["data"] == data
