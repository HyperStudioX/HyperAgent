"""Tests for error classification system."""

import pytest

from app.agents.tools.react_tool import ErrorCategory, classify_error


class TestErrorCategory:
    """Tests for ErrorCategory enum."""

    def test_enum_values(self):
        assert ErrorCategory.TRANSIENT == "transient"
        assert ErrorCategory.INPUT == "input"
        assert ErrorCategory.PERMISSION == "permission"
        assert ErrorCategory.RESOURCE == "resource"
        assert ErrorCategory.FATAL == "fatal"
        assert ErrorCategory.UNKNOWN == "unknown"


class TestClassifyError:
    """Tests for classify_error function."""

    # --- Transient errors ---

    def test_timeout_is_transient(self):
        assert classify_error("Connection timed out") == ErrorCategory.TRANSIENT

    def test_connection_error_is_transient(self):
        assert classify_error("ConnectionError: Unable to reach host") == ErrorCategory.TRANSIENT

    def test_rate_limit_is_transient(self):
        assert classify_error("429 Too Many Requests - Rate limit exceeded") == ErrorCategory.TRANSIENT

    def test_503_is_transient(self):
        assert classify_error("503 Service Temporarily Unavailable") == ErrorCategory.TRANSIENT

    # --- Input errors ---

    def test_validation_error_is_input(self):
        assert classify_error("Validation error: field 'url' is required") == ErrorCategory.INPUT

    def test_type_error_is_input(self):
        assert classify_error("TypeError: expected string, got int") == ErrorCategory.INPUT

    def test_syntax_error_is_input(self):
        assert classify_error("SyntaxError: unexpected token") == ErrorCategory.INPUT

    def test_bad_request_is_input(self):
        assert classify_error("400 Bad Request") == ErrorCategory.INPUT

    # --- Permission errors ---

    def test_permission_denied_is_permission(self):
        assert classify_error("Permission denied: /etc/shadow") == ErrorCategory.PERMISSION

    def test_forbidden_is_permission(self):
        assert classify_error("403 Forbidden") == ErrorCategory.PERMISSION

    def test_unauthorized_is_permission(self):
        assert classify_error("401 Unauthorized") == ErrorCategory.PERMISSION

    # --- Resource errors ---

    def test_not_found_is_resource(self):
        assert classify_error("404 Not Found") == ErrorCategory.RESOURCE

    def test_no_such_file_is_resource(self):
        assert classify_error("No such file or directory: /tmp/missing.txt") == ErrorCategory.RESOURCE

    def test_module_not_found_is_resource(self):
        assert classify_error("ModuleNotFoundError: No module named 'xyz'") == ErrorCategory.RESOURCE

    # --- Fatal errors ---

    def test_oom_is_fatal(self):
        assert classify_error("Out of memory") == ErrorCategory.FATAL

    def test_killed_is_fatal(self):
        assert classify_error("Process killed by signal 9") == ErrorCategory.FATAL

    # --- Unknown errors ---

    def test_empty_string_is_unknown(self):
        assert classify_error("") == ErrorCategory.UNKNOWN

    def test_generic_error_is_unknown(self):
        assert classify_error("Something went wrong") == ErrorCategory.UNKNOWN

    def test_case_insensitive(self):
        assert classify_error("CONNECTION TIMED OUT") == ErrorCategory.TRANSIENT
        assert classify_error("PERMISSION DENIED") == ErrorCategory.PERMISSION
