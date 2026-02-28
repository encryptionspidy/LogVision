"""Tests for app.ingestion.reader — streaming file reader."""

import pytest
from app.ingestion.reader import read_lines, validate_file, detect_encoding, ReaderError


class TestValidateFile:
    """Tests for file validation."""

    def test_valid_log_file(self, sample_log_path):
        path = validate_file(sample_log_path)
        assert path.exists()

    def test_valid_txt_file(self, tmp_log_file):
        p = tmp_log_file("some content", suffix=".txt")
        path = validate_file(p)
        assert path.exists()

    def test_nonexistent_file_raises(self):
        with pytest.raises(ReaderError, match="File not found"):
            validate_file("/nonexistent/file.log")

    def test_wrong_extension_raises(self, tmp_path):
        f = tmp_path / "test.csv"
        f.write_text("data")
        with pytest.raises(ReaderError, match="Unsupported file extension"):
            validate_file(str(f))

    def test_empty_file_raises(self, empty_log_path):
        with pytest.raises(ReaderError, match="File is empty"):
            validate_file(empty_log_path)

    def test_directory_raises(self, tmp_path):
        with pytest.raises(ReaderError, match="Not a regular file"):
            validate_file(str(tmp_path))


class TestDetectEncoding:
    """Tests for encoding detection."""

    def test_utf8_detection(self, sample_log_path):
        from pathlib import Path
        encoding = detect_encoding(Path(sample_log_path))
        assert encoding.lower().replace("-", "") in ("utf8", "ascii", "utf8sig")

    def test_fallback_on_empty(self, tmp_path):
        from pathlib import Path
        f = tmp_path / "empty_enc.log"
        f.write_bytes(b"")
        encoding = detect_encoding(f)
        assert encoding == "utf-8"


class TestReadLines:
    """Tests for streaming line reader."""

    def test_reads_all_lines(self, sample_log_path):
        lines = list(read_lines(sample_log_path))
        assert len(lines) > 0
        # Each element is (line_number, text)
        assert all(isinstance(ln, int) and isinstance(txt, str)
                    for ln, txt in lines)

    def test_line_numbers_start_at_1(self, sample_log_path):
        lines = list(read_lines(sample_log_path))
        assert lines[0][0] == 1

    def test_skips_empty_lines(self, tmp_log_file):
        content = "line1\n\n\nline4\n"
        p = tmp_log_file(content)
        lines = list(read_lines(p))
        assert len(lines) == 2
        assert lines[0][1] == "line1"
        assert lines[1][1] == "line4"

    def test_strips_newlines(self, tmp_log_file):
        content = "line with trailing\r\n"
        p = tmp_log_file(content)
        lines = list(read_lines(p))
        assert lines[0][1] == "line with trailing"

    def test_empty_file_raises(self, empty_log_path):
        with pytest.raises(ReaderError, match="File is empty"):
            list(read_lines(empty_log_path))

    def test_large_file_streams(self, large_log_path):
        """Verify large files can be processed without memory issues."""
        count = 0
        for _ in read_lines(large_log_path):
            count += 1
        assert count == 10_000
