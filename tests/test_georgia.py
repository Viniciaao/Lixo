"""Offline regression tests: no network, paid sources or game installation needed."""
import copy
import io
import json
import struct
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fetch_georgia import Fetcher, Links, PublicUnavailable, clean_name, public_attachments, sanitized_error
from georgia_validation import safe_member, sniff_extension, validate_dbpf, validate_file


def package():
    payload = bytearray(132)
    payload[:4] = b"DBPF"
    struct.pack_into("<II", payload, 4, 2, 1)
    struct.pack_into("<III", payload, 36, 1, 96, 36)
    struct.pack_into("<Q", payload, 64, 96)
    return bytes(payload)


class ValidationTests(unittest.TestCase):
    def test_rejects_error_pages_and_lfs_pointer(self):
        for content in (b"<html>" + b"x" * 2048, b' {"error":"login"}',
                        b"\xef\xbb\xbf<html>", b"version https://git-lfs.github.com/spec/v1\n"):
            with self.subTest(content=content[:20]), self.assertRaises(ValueError):
                sniff_extension(content)

    def test_dbpf_header_and_resource_index_bounds(self):
        data = package()
        validate_dbpf(data[:96], len(data))
        for head, size in ((data[:80], len(data)), (data[:96], 100), (b"NOPE" + data[4:96], len(data))):
            with self.assertRaises(ValueError):
                validate_dbpf(head, size)

    def test_unsafe_archive_paths(self):
        for name in ("../escape.package", "/tmp/a.package", "C:\\a.package", "a/../../b.package", "a\n.exe", "run.ts4script"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                safe_member(name)

    def test_package_checksum_and_zip_validation(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            direct = root / "a.package"
            direct.write_bytes(package())
            self.assertEqual(validate_file(direct)["format"], "package")
            archive = root / "a.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("cc.package", package())
            result = validate_file(archive)
            self.assertEqual(result["members"][0]["sha256"], validate_file(direct)["sha256"])
            with self.assertRaises(ValueError):
                validate_file(archive, household=True)

    def test_household_and_corrupt_zip(self):
        with tempfile.TemporaryDirectory() as root:
            archive = Path(root) / "household.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("a.trayitem", b"tray payload")
                z.writestr("b.householdbinary", b"household payload")
            self.assertEqual(validate_file(archive, household=True)["format"], "zip")
            contents = archive.read_bytes().replace(b"tray payload", b"bad! payload")
            archive.write_bytes(contents)
            with self.assertRaises(zipfile.BadZipFile):
                validate_file(archive)

    def test_zip_with_fake_package_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            archive = Path(root) / "bad.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("fake.package", b"<html>access denied</html>")
            with self.assertRaises(ValueError):
                validate_file(archive)


class SourceTests(unittest.TestCase):
    def document(self):
        return {"data": {"id": "42", "attributes": {"current_user_can_view": True},
                         "relationships": {"attachments_media": {"data": [{"id": "2"}, {"id": "1"}]}}},
                "included": [{"id": "cover", "type": "media", "attributes": {"file_name": "cover.jpg"}},
                             {"id": "1", "type": "media", "attributes": {"file_name": "right.package", "size_bytes": 132, "download_url": "https://example.com/right"}},
                             {"id": "2", "type": "media", "attributes": {"file_name": "other.package", "size_bytes": 234, "download_url": "https://example.com/other"}}]}

    def test_media_join_keeps_filename_and_url_together(self):
        result = public_attachments(self.document())
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "right.package")
        self.assertEqual(result[0]["url"], "https://example.com/right")
        self.assertEqual(result[0]["bytes"], 132)

    def test_locked_posts_are_never_downloaded(self):
        document = self.document()
        document["data"]["attributes"]["current_user_can_view"] = False
        with self.assertRaises(PublicUnavailable):
            public_attachments(document)

    def test_sfs_html_entities_and_nested_labels(self):
        parser = Links()
        parser.feed('<a href="/download/1/"><b>Default alpha</b> teeth all &amp; more</a>')
        self.assertEqual(parser.links, [("/download/1/", "Default alpha teeth all & more")])
        self.assertEqual(clean_name("Lighting 2.0 [COLOR].package"), "Lighting_2.0_COLOR_.package")

    def test_query_tokens_are_not_logged(self):
        text = sanitized_error("GET https://example.com/file?token=SECRET&expires=123 failed")
        self.assertNotIn("SECRET", text)
        self.assertIn("https://example.com/file", text)

    def test_failures_are_not_silently_successful(self):
        with tempfile.TemporaryDirectory() as root:
            fetcher = Fetcher(Path(root) / "pack", Path(root) / "work")
            with patch("builtins.print"):
                fetcher.attempt("01", lambda: None)
                self.assertEqual(fetcher.finish(), 1)
            self.assertEqual(fetcher.items["01"]["status"], "failed")
            self.assertEqual(fetcher.items["02"]["status"], "manual")
            self.assertFalse((Path(root) / "pack" / "SHA256SUMS.txt").read_text())
            fetcher.session.close()

    def test_partial_attachment_group_is_a_failure(self):
        with tempfile.TemporaryDirectory() as root:
            fetcher = Fetcher(Path(root) / "pack", Path(root) / "work")
            def partial():
                fetcher.items["07"]["files"].append({"path": "CCs/first.package"})
                raise ValueError("second attachment failed")
            with patch("builtins.print"):
                fetcher.attempt("07", partial)
            self.assertEqual(fetcher.items["07"]["status"], "failed")
            fetcher.session.close()

    def test_refuse_mixing_old_downloads(self):
        with tempfile.TemporaryDirectory() as root:
            fetcher = Fetcher(Path(root) / "pack", Path(root) / "work")
            (fetcher.out / "old.package").write_bytes(package())
            with self.assertRaises(ValueError):
                fetcher.run()
            fetcher.session.close()


if __name__ == "__main__":
    unittest.main()
