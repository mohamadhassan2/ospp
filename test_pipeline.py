import pipeline

def test_regex_replacement():
    data = {
        "message": "hello foo and secret info",
        "email": "user@example.com"
    }
    steps = [
        {"type": "regex_replace", "field": "message", "pattern": "foo", "replacement": "bar"},
        {"type": "regex_replace", "field": "message", "pattern": "secret", "replacement": "[REDACTED]"},
        {"type": "regex_replace", "field": "email", "pattern": ".+@.+", "replacement": "[email protected]"}
    ]
    result = pipeline.apply_pipeline(data, steps)
    assert result["message"] == "hello bar and [REDACTED] info"
    assert result["email"] == "[email protected]"
    print("[✓] Pipeline test passed!")

if __name__ == "__main__":
    test_regex_replacement()

