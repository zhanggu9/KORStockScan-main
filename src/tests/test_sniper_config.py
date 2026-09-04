from src.engine import sniper_config


def test_merge_openai_environment_overrides_file_keys_without_mutating_input():
    config = {
        "OPENAI_API_KEY": "file-key",
        "OPENAI_API_KEY_2": "file-key-2",
        "KIWOOM_APPKEY": "broker-key",
    }

    result = sniper_config._merge_openai_environment(
        config,
        {"OPENAI_API_KEY": "env-key"},
    )

    assert result == {"OPENAI_API_KEY": "env-key", "KIWOOM_APPKEY": "broker-key"}
    assert config["OPENAI_API_KEY"] == "file-key"


def test_merge_openai_environment_supports_comma_separated_keys():
    result = sniper_config._merge_openai_environment(
        {"OTHER": "value"},
        {"OPENAI_API_KEYS": " first-key, second-key ,, third-key "},
    )

    assert result == {
        "OTHER": "value",
        "OPENAI_API_KEY": "first-key",
        "OPENAI_API_KEY_2": "second-key",
        "OPENAI_API_KEY_3": "third-key",
    }


def test_merge_openai_environment_keeps_file_keys_when_environment_is_absent():
    config = {"OPENAI_API_KEY": "file-key", "OTHER": "value"}

    result = sniper_config._merge_openai_environment(config, {})

    assert result is config
