"""Bounded read-only DSM-CC reconstruction through the production core."""
import hashlib
from pathlib import Path
import unittest
import test_dsmcc_summaries as f


class DsmccReconstructionTests(unittest.TestCase):
    setUp=f.DsmccSummaryTests.setUp
    tearDown=f.DsmccSummaryTests.tearDown
    scan=f.DsmccSummaryTests.scan
    detail=f.DsmccSummaryTests.detail
    objects=f.DsmccSummaryTests.objects
    assert_evidence=f.DsmccSummaryTests.assert_evidence
    def run_sections(self,raws,**kwargs):
        self.scan([(0x150,r) if isinstance(r,bytes) else r for r in raws]);kwargs.setdefault('at_packet',self.state['packets']-1);return self.detail(**kwargs)['application_signalling']
    def module(self,summary,identifier=7):return next(x for x in self.objects(summary,'download_module') if x['identity']['module_id']==identifier)
    def status(self,summary,status,identifier=7):
        m=self.module(summary,identifier);self.assertEqual(m['attributes']['assembly_status'],status)
        if status!='complete':self.assertIsNone(m['attributes']['assembled_sha256'])
        return m
    def basic(self):return [f.dii(),f.ddb(b'abcd'),f.ddb(b'ef',block=1)]
    def test_complete_exact_bytes_hash_and_all_original_sources(self):
        s=self.run_sections(self.basic());self.assertEqual(s['status'],'ok');m=self.status(s,'complete');self.assertEqual(m['attributes']['assembled_sha256'],hashlib.sha256(b'abcdef').hexdigest());self.assertEqual(m['attributes']['received_block_count'],2);self.assertEqual(len(m['evidence']),3)
        self.assertEqual(m['attributes']['decompression_status'],'not_requested');self.assert_evidence(s)
    def test_descending_module_ids_pin_sdk_declaration_order(self):
        s=self.run_sections([f.dii([f.declaration(9,size=1),f.declaration(2,size=2)]),f.ddb(b'x',module=9),f.ddb(b'yz',module=2)])
        self.assertEqual(self.status(s,'complete',9)['attributes']['assembled_sha256'],hashlib.sha256(b'x').hexdigest());self.status(s,'complete',2)
    def test_missing_block_and_exact_final_length(self):
        for blocks,status in [([f.ddb(b'abcd')],'incomplete'),([f.ddb(b'abcd'),f.ddb(b'efgh',block=1)],'conflict'),([f.ddb(b'abcd'),f.ddb(b'e',block=1)],'conflict'),([f.ddb(b'abcd'),f.ddb(b'ef',block=2)],'conflict')]:
            with self.subTest(status=status,length=len(blocks[-1])):self.status(self.run_sections([f.dii(),*blocks]),status)
    def test_identical_duplicate_blocks_are_retained_without_conflict(self):
        s=self.run_sections(self.basic()+[f.ddb(b'abcd',version=4),f.ddb(b'abcd')]);m=self.status(s,'complete');self.assertEqual(m['attributes']['duplicate_block_observations'],2);self.assertEqual(m['attributes']['contributing_source_count'],4);self.assert_evidence(s)
    def test_conflicting_duplicate_blocks_never_hash(self):
        s=self.run_sections(self.basic()+[f.ddb(b'ABCD')]);self.status(s,'conflict');self.assert_evidence(s)
    def test_same_version_size_block_size_or_info_disagreement_is_sticky(self):
        for changed in [f.dii([f.declaration(size=7)]),f.dii(block_size=3),f.dii([f.declaration(info=b'')])]:
            with self.subTest(changed=changed.hex()):self.status(self.run_sections(self.basic()+[changed,f.dii()]),'conflict')
    def test_orphan_blocks_are_not_replayed_after_announcement(self):
        s=self.run_sections([f.ddb(b'abcd'),f.dii(),f.ddb(b'ef',block=1)]);self.status(s,'incomplete');self.assertEqual(s['module_snapshot']['orphan_block_observations'],1)
        s=self.run_sections([f.ddb(b'abcd'),f.dii(),f.ddb(b'ef',block=1),f.ddb(b'abcd')]);self.status(s,'complete')
    def test_version_reuse_starts_new_epoch_without_old_blocks(self):
        s=self.run_sections(self.basic()+[f.dii([f.declaration(version=4)]),f.dii()]);m=self.status(s,'incomplete');self.assertEqual(m['attributes']['received_block_count'],0);self.assertGreater(m['identity']['announcement_epoch_order'],1)
        s=self.run_sections(self.basic()+[f.dii([f.declaration(version=4)]),f.dii(),f.ddb(b'abcd'),f.ddb(b'ef',block=1)]);self.status(s,'complete')
    def test_identical_announcement_repetition_preserves_epoch(self):
        s=self.run_sections(self.basic()+[f.dii(transaction=4),f.dii()]);m=self.status(s,'complete');self.assertEqual(m['identity']['announcement_epoch_packet'],0);self.assertEqual(m['attributes']['contributing_source_count'],4)
    def test_partial_dii_does_not_withdraw_other_modules(self):
        s=self.run_sections([f.dii([f.declaration(7),f.declaration(8,size=1)]),f.ddb(b'x',module=8),f.dii([f.declaration(7)]),f.ddb(b'abcd'),f.ddb(b'ef',block=1)]);self.status(s,'complete');self.status(s,'complete',8)
    def test_pid_download_id_and_module_version_never_cross_join(self):
        s=self.run_sections([f.dii(),(0x151,f.ddb(b'abcd')),f.ddb(b'abcd',download=42),f.ddb(b'abcd',module_version=4),f.ddb(b'ef',block=1)]);m=self.status(s,'incomplete');self.assertEqual(m['attributes']['received_block_count'],1)
    def test_same_packet_order_distinguishes_orphan_from_contribution(self):
        for raw,status in [(f.ddb(b'abcd')+f.dii()+f.ddb(b'ef',block=1),'incomplete'),(f.dii()+f.ddb(b'abcd')+f.ddb(b'ef',block=1),'complete')]:
            s=self.run_sections([raw]);self.status(s,status);self.assertEqual(self.state['packets'],1)
    def test_default_inspect_cutoff_remains_last_occurrence_of_source(self):
        self.run_sections(self.basic());s=self.detail(index=0)['application_signalling'];self.status(s,'incomplete');self.assertEqual(s['at_packet'],0)
    def test_cutoff_uses_completion_not_first_packet(self):
        s=self.run_sections([f.dii([f.declaration(size=1000)],block_size=1000),f.ddb(b'x'*1000)],index=0,at_packet=1);self.status(s,'incomplete')
        s=self.detail(index=0,at_packet=self.state['packets']-1)['application_signalling'];self.status(s,'complete')
    def test_reanalysis_changes_identity_and_rejects_old_revision(self):
        s=self.run_sections(self.basic());old=self.module(s)['node_id'];revision=s['analysis_revision'];s=self.run_sections(self.basic());self.assertNotEqual(old,self.module(s)['node_id'])
        with self.assertRaises(RuntimeError):self.detail(analysis_revision=revision)
    def test_limits_and_overflow_never_produce_hash(self):
        for size,block in [(16*1024*1024+1,4064),(0xffffffff,65535),(2048,1),(46902304,4064)]:
            with self.subTest(size=size,block=block):
                m=self.status(self.run_sections([f.dii([f.declaration(size=size)],block_size=block)]),'resource_limit');self.assertEqual(m['attributes']['expected_block_count'],(size+block-1)//block)
        self.status(self.run_sections([f.dii(block_size=0)]),'invalid_announcement')
    def test_oversized_announcements_do_not_spend_independent_hash_budget(self):
        s=self.run_sections([f.dii([f.declaration(1,size=80*1024*1024),f.declaration(7)]),f.ddb(b'abcd'),f.ddb(b'ef',block=1)]);self.status(s,'resource_limit',1);self.status(s,'complete');self.assertNotEqual(s['module_snapshot']['status'],'resource_limit')
        s=self.run_sections([f.dii([f.declaration(i,size=16*1024*1024) for i in range(5)])]);self.assertNotEqual(s['module_snapshot']['status'],'resource_limit');self.assertTrue(all(x['attributes']['assembly_status']=='resource_limit' and x['attributes']['assembled_sha256'] is None for x in self.objects(s,'download_module')))
    def test_reused_records_link_post_epoch_occurrences(self):
        s=self.run_sections(self.basic()+[f.dii([f.declaration(version=4)]),f.dii(),f.ddb(b'abcd'),f.ddb(b'ef',block=1)]);m=self.status(s,'complete');self.assertEqual(m['identity']['announcement_epoch_packet'],4)
        self.assertEqual(sorted(e['occurrence']['completion_packet'] for e in m['evidence']),[4,5,6])
        self.assertTrue(all(e['occurrence']['completion_order']>=m['identity']['announcement_epoch_order'] for e in m['evidence']));self.assert_evidence(s)
    def test_duplicate_module_declarations_preserve_conflict_and_versions(self):
        s=self.run_sections([f.dii([f.declaration(),f.declaration(version=4)]),f.ddb(b'abcd'),f.ddb(b'ef',block=1)]);m=self.status(s,'conflict');self.assertEqual(m['attributes']['module_version_candidates'],[3,4])
    def test_repeated_duplicate_version_candidates_are_not_forgotten(self):
        raw=f.dii([f.declaration(),f.declaration(version=4)])
        s=self.run_sections([raw,raw,f.ddb(b'abcd'),f.ddb(b'ef',block=1)]);m=self.status(s,'conflict');self.assertEqual(m['attributes']['module_version_candidates'],[3,4])
    def test_repeated_dii_declaration_work_is_bounded_before_iteration(self):
        raw=f.dii([f.declaration(i,info=b'') for i in range(256)])
        s=self.run_sections([raw]*257);self.assertEqual(s['status'],'resource_limit');self.assertIn('65536',' '.join(s['diagnostics']))
    def test_malformed_replacement_and_unsupported_cancel_block_reconstruction(self):
        for raw in [f.recalc(f.dii()[:-5]+b'\0'*4),f.message(0x3b,f.dword(0x10203040),message_id=0x1005)]:
            s=self.run_sections(self.basic()+[raw],index=0);self.status(s,'unresolved');self.assert_evidence(s)
    def test_unresolved_ddb_identity_blocks_hash_with_exact_source(self):
        adapted=bytearray(f.ddb(b'abcd'));adapted[17]=1;adapted[20]=0x42
        for raw in [f.recalc(adapted),f.message(0x3c,b'')]:
            s=self.run_sections(self.basic()+[raw],index=0);self.status(s,'unresolved');self.assert_evidence(s)
            s=self.run_sections([raw]+self.basic());self.status(s,'complete')
    def test_empty_modules_are_explicitly_unsupported(self):
        self.status(self.run_sections([f.dii([f.declaration(size=0)])]),'unsupported_empty_module')
    def test_no_announcement_keeps_orphan_source_card_without_hash(self):
        s=self.run_sections([f.ddb(b'abcd')]);self.assertEqual(s['status'],'incomplete');self.assertFalse(self.objects(s,'download_module'));self.assertEqual(s['module_snapshot']['orphan_block_observations'],1);self.assert_evidence(s)
    def test_malformed_ddb_is_conflict_with_navigable_source(self):
        raw=bytearray(f.ddb(b'abcd'));raw[23]=0;raw=f.recalc(raw)
        s=self.run_sections(self.basic()+[raw],index=0);self.status(s,'conflict');self.assert_evidence(s)
    def test_next_messages_and_invalid_crc_do_not_contribute(self):
        bad=bytearray(f.ddb(b'ef',block=1));bad[-1]^=1
        s=self.run_sections([f.dii(),f.ddb(b'abcd'),f.ddb(b'ef',block=1,current=False),bytes(bad)],index=0);self.status(s,'incomplete')
        s=self.detail(index=2)['application_signalling'];self.assertFalse(self.objects(s,'download_module'))
    def test_distinct_repeated_announcements_hit_source_cap_without_hash(self):
        s=self.run_sections([f.dii(transaction=i) for i in range(2049)]+[f.ddb(b'abcd'),f.ddb(b'ef',block=1)]);m=self.status(s,'resource_limit');self.assertEqual(m['attributes']['contributing_source_count'],2048)
    def test_module_identity_cap_prevents_partial_success(self):
        s=self.run_sections([f.dii([f.declaration(i,size=1) for i in range(128)],block_size=1),f.dii([f.declaration(i,size=1) for i in range(128,256)],block_size=1),f.dii([f.declaration(256,size=1)],block_size=1)]);self.assertEqual(s['status'],'resource_limit');self.assertEqual(len(self.objects(s,'download_module')),256)

if __name__=='__main__':unittest.main()
