"""Tests for text normalization functions."""


from tbcrawl.normalization import (
    compute_button_signature,
    compute_screen_signature,
    detect_input_required,
    normalize_numbers,
    normalize_text,
    normalize_whitespace,
    truncate_text,
)


class TestNormalizeWhitespace:
    """Tests for whitespace normalization."""

    def test_collapses_multiple_spaces(self) -> None:
        """Multiple spaces should become one."""
        assert normalize_whitespace("hello   world") == "hello world"

    def test_collapses_newlines(self) -> None:
        """Newlines should become spaces."""
        assert normalize_whitespace("hello\n\nworld") == "hello world"

    def test_strips_edges(self) -> None:
        """Leading/trailing whitespace should be removed."""
        assert normalize_whitespace("  hello world  ") == "hello world"

    def test_handles_tabs(self) -> None:
        """Tabs should be normalized."""
        assert normalize_whitespace("hello\t\tworld") == "hello world"

    def test_handles_mixed(self) -> None:
        """Mixed whitespace should be normalized."""
        assert normalize_whitespace("  hello\n\t  world  \n") == "hello world"


class TestNormalizeNumbers:
    """Tests for number normalization."""

    def test_replaces_single_digit(self) -> None:
        """Single digit should be replaced."""
        assert normalize_numbers("Order 5") == "Order #"

    def test_replaces_multiple_digits(self) -> None:
        """Multiple consecutive digits become single #."""
        assert normalize_numbers("Order 12345") == "Order #"

    def test_replaces_multiple_occurrences(self) -> None:
        """All number sequences should be replaced."""
        assert normalize_numbers("Order 123 costs 456 USD") == "Order # costs # USD"

    def test_preserves_text(self) -> None:
        """Non-numeric text should be preserved."""
        assert normalize_numbers("Hello World") == "Hello World"

    def test_handles_no_numbers(self) -> None:
        """Text without numbers should be unchanged."""
        result = normalize_numbers("No numbers here!")
        assert result == "No numbers here!"


class TestNormalizeText:
    """Tests for full text normalization."""

    def test_combines_all_normalizations(self) -> None:
        """All normalizations should be applied."""
        text = "  Order  12345\nTotal: 999  "
        result = normalize_text(text)
        assert result == "order # total: #"

    def test_lowercases(self) -> None:
        """Text should be lowercased."""
        assert normalize_text("HELLO World") == "hello world"

    def test_optional_number_replacement(self) -> None:
        """Number replacement can be disabled."""
        result = normalize_text("Order 123", replace_numbers=False)
        assert result == "order 123"


class TestComputeButtonSignature:
    """Tests for button signature computation."""

    def test_single_row(self) -> None:
        """Single row of buttons."""
        buttons = [[{"text": "A", "url": None}, {"text": "B", "url": None}]]
        result = compute_button_signature(buttons)
        assert result == "A|B"

    def test_multiple_rows(self) -> None:
        """Multiple rows of buttons."""
        buttons = [
            [{"text": "A", "url": None}],
            [{"text": "B", "url": None}, {"text": "C", "url": None}],
        ]
        result = compute_button_signature(buttons)
        assert result == "A;B|C"

    def test_empty_buttons(self) -> None:
        """Empty button list."""
        result = compute_button_signature([])
        assert result == ""

    def test_ignores_urls(self) -> None:
        """URLs should not affect signature."""
        buttons1 = [[{"text": "Link", "url": "https://a.com"}]]
        buttons2 = [[{"text": "Link", "url": "https://b.com"}]]
        assert compute_button_signature(buttons1) == compute_button_signature(buttons2)


class TestComputeScreenSignature:
    """Tests for screen signature computation."""

    def test_same_content_same_hash(self) -> None:
        """Same content should produce same hash."""
        buttons = [[{"text": "A", "url": None}]]
        sig1 = compute_screen_signature("Hello", buttons, False)
        sig2 = compute_screen_signature("Hello", buttons, False)
        assert sig1 == sig2

    def test_different_text_different_hash(self) -> None:
        """Different text should produce different hash."""
        buttons = [[{"text": "A", "url": None}]]
        sig1 = compute_screen_signature("Hello", buttons, False)
        sig2 = compute_screen_signature("World", buttons, False)
        assert sig1 != sig2

    def test_numbers_normalized_in_hash(self) -> None:
        """Numbers should be normalized before hashing."""
        buttons = [[{"text": "A", "url": None}]]
        sig1 = compute_screen_signature("Order 123", buttons, False)
        sig2 = compute_screen_signature("Order 456", buttons, False)
        assert sig1 == sig2

    def test_media_affects_hash(self) -> None:
        """Media presence should affect hash."""
        buttons = [[{"text": "A", "url": None}]]
        sig1 = compute_screen_signature("Hello", buttons, has_media=False)
        sig2 = compute_screen_signature("Hello", buttons, has_media=True)
        assert sig1 != sig2

    def test_hash_length(self) -> None:
        """Hash should be 16 characters (hex)."""
        sig = compute_screen_signature("Test", [], False)
        assert len(sig) == 16


class TestDetectInputRequired:
    """Tests for input detection."""

    def test_detects_russian_indicators(self) -> None:
        """Should detect Russian input indicators."""
        indicators = ["введите", "укажи", "напишите"]

        assert detect_input_required("Введите ваше имя", indicators)
        assert detect_input_required("Укажи количество", indicators)
        assert detect_input_required("Напишите сообщение", indicators)

    def test_case_insensitive(self) -> None:
        """Detection should be case-insensitive."""
        indicators = ["введите"]
        assert detect_input_required("ВВЕДИТЕ имя", indicators)
        assert detect_input_required("ВвЕдИтЕ имя", indicators)

    def test_returns_false_for_no_indicators(self) -> None:
        """Should return False when no indicators present."""
        indicators = ["введите", "укажи"]
        assert not detect_input_required("Выберите вариант", indicators)

    def test_empty_indicators_returns_false(self) -> None:
        """Empty indicators list should always return False."""
        assert not detect_input_required("Введите что-нибудь", [])


class TestTruncateText:
    """Tests for text truncation."""

    def test_short_text_unchanged(self) -> None:
        """Short text should not be modified."""
        assert truncate_text("Hello", 100) == "Hello"

    def test_exact_length_unchanged(self) -> None:
        """Text at exact max length should not be modified."""
        text = "a" * 50
        assert truncate_text(text, 50) == text

    def test_long_text_truncated(self) -> None:
        """Long text should be truncated with ellipsis."""
        text = "a" * 100
        result = truncate_text(text, 50)
        assert len(result) == 50
        assert result.endswith("...")

    def test_default_max_length(self) -> None:
        """Default max length is 100."""
        text = "a" * 150
        result = truncate_text(text)
        assert len(result) == 100
