import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from isobath.auth import decode_token

ISS, AUD = "https://x.supabase.co/auth/v1", "authenticated"
KEY = ec.generate_private_key(ec.SECP256R1())
PUB = KEY.public_key()


def token(key=KEY, alg="ES256", **over):
    claims = {"sub": str(uuid.uuid4()), "iss": ISS, "aud": AUD, "exp": int(time.time()) + 60}
    claims.update(over)
    return jwt.encode({k: v for k, v in claims.items() if v is not None}, key, algorithm=alg)


def test_valid():
    assert decode_token(token(), PUB, ISS, AUD)["aud"] == AUD


@pytest.mark.parametrize(
    "tok",
    [
        token(exp=int(time.time()) - 10),
        token(iss="https://evil/auth/v1"),
        token(aud="anon"),
        token(sub=None),
        token(sub="not-a-uuid"),
        token(key="shared-secret", alg="HS256"),
        token(key=None, alg="none"),
    ],
)
def test_rejected(tok):
    with pytest.raises((jwt.PyJWTError, ValueError, KeyError)):
        decode_token(tok, PUB, ISS, AUD)
