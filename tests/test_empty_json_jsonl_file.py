from base_for_compressed_file import (COMPRESSION_FOLDER_PATH, S3CompressedFile)
import tap_tester.connections as connections
import tap_tester.menagerie   as menagerie
import tap_tester.runner      as runner

class S3EmptyJsonJsonlFile(S3CompressedFile):

    def resource_names(self):
        return ["empty_json.jsonl","multiple_empty_json.jsonl"]

    def name(self):
        return "test_empty_json_jsonl_file"

    def expected_check_streams(self):
        return {
            'empty_json_jsonl_file'
        }

    def expected_sync_streams(self):
        return {
            'empty_json_jsonl_file'
        }

    def get_properties(self):
        properties = super().get_properties()
        properties["tables"] = "[{\"table_name\": \"empty_json_jsonl_file\",\"search_prefix\": \"jsonl_files_empty_json_jsonl_file\",\"search_pattern\": \"jsonl_files_empty_json_jsonl_file\\\\/.*\\\\.jsonl\"}]"
        return properties


    def test_run(self):

        self.setUpTestEnvironment("tap-s3-csv")

        runner.run_check_job_and_check_status(self)

        found_catalogs = menagerie.get_catalogs(self.conn_id)
        self.assertEqual(len(found_catalogs), 1, msg="unable to locate schemas for connection {}".format(self.conn_id))

        found_catalog_names = set(map(lambda c: c['tap_stream_id'], found_catalogs))
        subset = self.expected_check_streams().issubset( found_catalog_names )
        self.assertTrue(subset, msg="Expected check streams are not subset of discovered catalog")

        # Clear state before our run
        menagerie.set_state(self.conn_id, {})

        self.select_specific_catalog(found_catalogs, "empty_json_jsonl_file")

        runner.run_sync_job_and_check_status(self)

        expected_records = 0
        # Verify actual rows were synced
        records  = runner.get_upserts_from_target_output()

        self.assertEqual(expected_records, len(records))
