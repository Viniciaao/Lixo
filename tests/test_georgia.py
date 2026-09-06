"""Offline regression tests: no network, paid sources or game installation needed."""
import copy
import json
import struct
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fetch_georgia import SOURCES, Fetcher, Links, PublicUnavailable, attachment_selected, clean_name, post_link_urls, public_attachments, sanitized_error
from georgia_validation import safe_member, sniff_extension, validate_dbpf, validate_file
from package_georgia import check_manifest, render, verify_payloads


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


class DownloadTests(unittest.TestCase):
    def response(self, data):
        response = MagicMock()
        response.__enter__.return_value = response
        response.iter_content.return_value = [data]
        return response

    def test_atomic_download_and_dotted_filename(self):
        with tempfile.TemporaryDirectory() as root:
            fetcher = Fetcher(Path(root) / "pack", Path(root) / "work")
            with patch.object(fetcher, "get", return_value=self.response(package())), patch("builtins.print"):
                fetcher.download("13", "https://example.com/file", "13_Lighting_2.0_COLOR", "https://example.com/post", len(package()))
            self.assertTrue((fetcher.out / "13_Lighting_2.0_COLOR.package").exists())
            self.assertFalse(list(fetcher.out.glob("*.part")))
            fetcher.session.close()

    def test_bad_size_and_html_leave_no_files(self):
        for data, expected in ((package(), 999), (b"<html>error</html>", None)):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as root:
                fetcher = Fetcher(Path(root) / "pack", Path(root) / "work")
                with patch.object(fetcher, "get", return_value=self.response(data)), self.assertRaises(ValueError):
                    fetcher.download("13", "https://example.com/file", "13_test", "https://example.com/post", expected)
                self.assertFalse(list(fetcher.out.iterdir()))
                self.assertFalse(fetcher.items["13"]["files"])
                fetcher.session.close()

    def test_bodycare_excludes_male_names(self):
        pattern = r"FEMALE|CLEAVAGE|BODY[\s_]*PRESET"
        for name in ("FEMALE BODY PRESET.package", "FEMALE_BODY_PRESET.package", "CLEAVAGE MASK.package"):
            self.assertTrue(attachment_selected("16", name, pattern))
        for name in ("MALE BODY PRESET.package", "MALE_BODY_PRESET.package", "FEMALE.jpg"):
            self.assertFalse(attachment_selected("16", name, pattern))

    def test_drive_nested_folders_and_cycle(self):
        with tempfile.TemporaryDirectory() as root:
            fetcher = Fetcher(Path(root) / "pack", Path(root) / "work")
            pages = {
                "root": '<a href="https://drive.google.com/drive/folders/child">Child</a><a href="https://evil.example/file/d/evil/view">evil.package</a>',
                "child": '<a href="https://drive.google.com/drive/folders/root">Root</a><a href="https://drive.google.com/file/d/valid/view">mask.package</a>',
            }
            def get(url):
                fid = url.split("id=", 1)[1].split("#", 1)[0]
                return MagicMock(text=pages[fid])
            with patch.object(fetcher, "get", side_effect=get):
                self.assertEqual(fetcher.gdrive_files("root"), {"valid": "mask.package"})
            self.assertEqual(fetcher.items["20"]["resolved_folders"], ["child", "root"])
            fetcher.session.close()

    def test_sfs_missing_variant_fails_before_download(self):
        with tempfile.TemporaryDirectory() as root:
            fetcher = Fetcher(Path(root) / "pack", Path(root) / "work")
            page = '<a href="/download/1/">Non-default alpha teeth.zip</a>'
            with patch.object(fetcher, "get", return_value=MagicMock(text=page)), patch.object(fetcher, "fetch_sfs") as download:
                with self.assertRaises(ValueError):
                    fetcher.fetch_teeth()
                download.assert_not_called()
            fetcher.session.close()

    def test_patreon_rich_text_links_not_image_urls(self):
        url = "http://simfileshare.net/folder/66108/"
        document = {"type": "doc", "content": [
            {"type": "text", "marks": [{"type": "link", "attrs": {"href": url}}]},
            {"type": "image", "attrs": {"src": "https://example.com/image?token=secret"}},
        ]}
        self.assertEqual(post_link_urls({"content": None, "content_json_string": json.dumps(document)}), [url])

    def test_nosemask_follows_only_authors_expected_sfs_link(self):
        with tempfile.TemporaryDirectory() as root:
            fetcher = Fetcher(Path(root) / "pack", Path(root) / "work")
            document = {"data": {"id": "26574490", "attributes": {
                "current_user_can_view": True, "content": '<a href="http://simfileshare.net/folder/66108/">DL</a>'}}, "included": []}
            response = MagicMock()
            response.json.return_value = document
            with patch.object(fetcher, "get", return_value=response), patch.object(fetcher, "fetch_sfs_folder") as folder, patch("builtins.print"):
                fetcher.fetch_patreon("26574490", "21", "nosemask", None)
                self.assertEqual(folder.call_args.args[0], "66108")
                document["data"]["attributes"]["content"] = None
                document["data"]["attributes"]["content_json_string"] = json.dumps({
                    "type": "doc", "content": [{"type": "text", "marks": [{"type": "link", "attrs": {"href": "http://simfileshare.net/folder/66108/"}}]}]})
                fetcher.fetch_patreon("26574490", "21", "nosemask", None)
                self.assertEqual(folder.call_count, 2)
                document["data"]["attributes"]["content_json_string"] = None
                document["data"]["attributes"]["content"] = '<a href="https://evil.example/folder/66108/">DL</a>'
                with self.assertRaises(ValueError):
                    fetcher.fetch_patreon("26574490", "21", "nosemask", None)
            fetcher.session.close()


class PackagingTests(unittest.TestCase):
    def manifest(self):
        items = [{**copy.deepcopy(source), "status": "manual", "files": [], "errors": []} for source in SOURCES]
        return {"schema_version": 1, "generated_at": "2026-09-06T00:00:00+00:00", "checkout_sha": "0" * 40,
                "workflow_run": "https://github.com/Viniciaao/Lixo/actions/runs/123", "items": items,
                "summary": {"files": 0, "bytes": 0, "downloaded": 0, "manual": 21, "failed": 0}}

    def test_documentation_is_reproducible_and_honest(self):
        manifest = self.manifest()
        output = render(manifest)
        self.assertEqual(output, render(manifest))
        self.assertEqual(output["SHA256SUMS.txt"], "")
        self.assertIn("21 manuais", output["README.md"])
        self.assertIn("90 dias", output["README.md"])
        self.assertIn("não estão em blobs Git", output["README.md"])
        self.assertIn("115736891", output["INSTALACAO-MANUAL.txt"])
        self.assertNotIn("modsfire.com", output["LINKS-ORIGINAIS.txt"])
        for text in output.values():
            if text:
                self.assertTrue(text.endswith("\n"))
                self.assertFalse(text.endswith("\n\n"))

    def test_missing_source_and_false_summary_are_rejected(self):
        manifest = self.manifest()
        manifest["items"].pop()
        with self.assertRaises(ValueError):
            check_manifest(manifest)
        manifest = self.manifest()
        manifest["summary"]["files"] = 1
        with self.assertRaises(ValueError):
            check_manifest(manifest)

    def test_verify_refuses_unlisted_payloads(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            (root / "CCs").mkdir()
            (root / "CCs" / "extra.package").write_bytes(package())
            with self.assertRaises(ValueError):
                verify_payloads(root, self.manifest())


if __name__ == "__main__":
    unittest.main()
