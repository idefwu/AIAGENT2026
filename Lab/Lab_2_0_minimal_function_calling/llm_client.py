from openai import OpenAI


def create_client():
    # /api/v1,/api/chat/completions
    client = OpenAI(
        base_url="http://localhost:8080/api/v1",
        api_key="sk-1540f219fcb246b9bb55c7951491c01b"
    )

    return client