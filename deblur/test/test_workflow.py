# -----------------------------------------------------------------------------
# Copyright (c) 2015, The Deblur Development Team.
#
# Distributed under the terms of the BSD 3-clause License.
#
# The full license is in the file LICENSE, distributed with this software.
# -----------------------------------------------------------------------------

from unittest import TestCase, main
from shutil import rmtree
from tempfile import mkdtemp
from os import listdir
from types import GeneratorType
from os.path import join, isfile, abspath, dirname, splitext

from skbio.util import remove_files
from skbio.parse.sequences import parse_fasta
from skbio.alignment import SequenceCollection
from skbio import DNA

from biom import load_table
import logging

from deblur.workflow import (dereplicate_seqs,
                             remove_chimeras_denovo_from_seqs,
                             remove_artifacts_seqs,
                             create_otu_table,
                             get_files_for_table,
                             trim_seqs,
                             multiple_sequence_alignment,
                             launch_workflow,
                             split_sequence_file_on_sample_ids_to_files,
                             build_index_sortmerna,
                             start_log,
                             sample_id_from_read_id)


class workflowTests(TestCase):
    """ Test deblur pipeline and individual methods functionality """

    def setUp(self):
        """ Create working directory and two FASTA input
            files corresponding to two samples (s1 and s2).
            Each input file contains 120 sequences, of which
            100 are 16S amplicons (ART simulator), 10 are
            chimeric sequences (Grinder) and 10 are PhiX
            artifacts (ART). The 100 amplicon sequences
            intend to evenly represent a community of 10
            species.
        """
        # test output can be written to this directory
        self.working_dir = mkdtemp()

        # the data directory for the workflow test files
        self.test_data_dir = join(dirname(abspath(__file__)), 'data')
        self.seqs_s1_fp = join(self.test_data_dir, 'seqs_s1.fasta')
        self.seqs_s2_fp = join(self.test_data_dir, 'seqs_s2.fasta')
        self.seqs_s3_fp = join(self.test_data_dir, 'seqs_s3.fasta')
        self.orig_s1_fp = join(self.test_data_dir, 'simset.s1.fasta')
        self.orig_s2_fp = join(self.test_data_dir, 'simset.s2.fasta')
        self.orig_s3_fp = join(self.test_data_dir, 'simset.s3.fasta')

        self.files_to_remove = []

        logfilename = join(self.working_dir, "log.txt")
        start_log(level=logging.DEBUG, filename=logfilename)

    def tearDown(self):
        remove_files(self.files_to_remove)
        rmtree(self.working_dir)

    def test_trim_seqs(self):
        seqs = [("seq1", "tagggcaagactccatggtatga"),
                ("seq2", "cggaggcgagatgcgtggta"),
                ("seq3", "tactagcaagattcctggtaaagga"),
                ("seq4", "aggatgcgagatgcgtg"),
                ("seq5", "gagtgcgagatgcgtggtgagg"),
                ("seq6", "ggatgcgagatgcgtggtgatt"),
                ("seq7", "agggcgagattcctagtgga--")]
        obs = trim_seqs(seqs, 20)

        self.assertTrue(isinstance(obs, GeneratorType))

        exp = [("seq1", "tagggcaagactccatggta"),
               ("seq2", "cggaggcgagatgcgtggta"),
               ("seq3", "tactagcaagattcctggta"),
               ("seq5", "gagtgcgagatgcgtggtga"),
               ("seq6", "ggatgcgagatgcgtggtga"),
               ("seq7", "agggcgagattcctagtgga")]
        self.assertEqual(list(obs), exp)

    def test_dereplicate_seqs_remove_singletons(self):
        """ Test dereplicate_seqs() method functionality with
            removing singletons
        """
        seqs = [("seq1", "TACCGGCAGCTCAAGTGATGACCGCTATTATTGGGCCTAAAGCGTCCG"),
                ("seq2", "TACCGGCAGCTCAAGTGATGACCGCTATTATTGGGCCTAAAGCGTCCG"),
                ("seq3", "TACCGGCAGCTCAAGTGATGACCGCTATTATTGGGCCTAAAGCGTCCG"),
                ("seq4", "TACCGGCAGCTCAAGTGATGACCGCTATTATTGGGCCTAAAGCGTCCT"),
                ("seq5", "TACCAGCCCCTTAAGTGGTAGGGACGATTATTTGGCCTAAAGCGTCCG"),
                ("seq6", "CTGCAAGGCTAGGGGGCGGGAGAGGCGGGTGGTACTTGAGGGGAGAAT"),
                ("seq7", "CTGCAAGGCTAGGGGGCGGGAGAGGCGGGTGGTACTTGAGGGGAGAAT")]
        seqs_fp = join(self.working_dir, "seqs.fasta")
        with open(seqs_fp, 'w') as seqs_f:
            for seq in seqs:
                seqs_f.write(">%s\n%s\n" % seq)

        output_fp = join(self.working_dir, "seqs_derep.fasta")

        dereplicate_seqs(seqs_fp=seqs_fp,
                         output_fp=output_fp)
        self.assertTrue(isfile(output_fp))

        exp = [("seq1;size=3;",
                "TACCGGCAGCTCAAGTGATGACCGCTATTATTGGGCCTAAAGCGTCCG"),
               ("seq6;size=2;",
                "CTGCAAGGCTAGGGGGCGGGAGAGGCGGGTGGTACTTGAGGGGAGAAT")]

        with open(output_fp, 'U') as out_f:
            act = [item for item in parse_fasta(out_f)]

        self.assertEqual(act, exp)

    def test_dereplicate_seqs(self):
        """ Test dereplicate_seqs() method functionality,
            keep singletons
        """
        seqs = [("seq1", "TACCGGCAGCTCAAGTGATGACCGCTATTATTGGGCCTAAAGCGTCCG"),
                ("seq2", "TACCGGCAGCTCAAGTGATGACCGCTATTATTGGGCCTAAAGCGTCCG"),
                ("seq3", "TACCGGCAGCTCAAGTGATGACCGCTATTATTGGGCCTAAAGCGTCCG"),
                ("seq4", "TACCGGCAGCTCAAGTGATGACCGCTATTATTGGGCCTAAAGCGTCCT"),
                ("seq5", "TACCAGCCCCTTAAGTGGTAGGGACGATTATTTGGCCTAAAGCGTCCG"),
                ("seq6", "CTGCAAGGCTAGGGGGCGGGAGAGGCGGGTGGTACTTGAGGGGAGAAT"),
                ("seq7", "CTGCAAGGCTAGGGGGCGGGAGAGGCGGGTGGTACTTGAGGGGAGAAT")]
        seqs_fp = join(self.working_dir, "seqs.fasta")
        with open(seqs_fp, 'w') as seqs_f:
            for seq in seqs:
                seqs_f.write(">%s\n%s\n" % seq)

        output_fp = join(self.working_dir, "seqs_derep.fasta")

        dereplicate_seqs(seqs_fp=seqs_fp,
                         output_fp=output_fp,
                         min_size=1)
        self.assertTrue(isfile(output_fp))

        exp = [("seq1;size=3;",
                "TACCGGCAGCTCAAGTGATGACCGCTATTATTGGGCCTAAAGCGTCCG"),
               ("seq6;size=2;",
                "CTGCAAGGCTAGGGGGCGGGAGAGGCGGGTGGTACTTGAGGGGAGAAT"),
               ("seq4;size=1;",
                "TACCGGCAGCTCAAGTGATGACCGCTATTATTGGGCCTAAAGCGTCCT"),
               ("seq5;size=1;",
                "TACCAGCCCCTTAAGTGGTAGGGACGATTATTTGGCCTAAAGCGTCCG")]

        with open(output_fp, 'U') as out_f:
            act = [item for item in parse_fasta(out_f)]

        self.assertEqual(act, exp)

    def test_remove_artifacts_seqs(self):
        """ Test remove_artifacts_seqs() function for removing
            sequences not matching to a reference database
            using SortMeRNA. This test forces a new index
            construction for the reference sequences.
        """
        seqs = [("seq1", "TACCCGCAGCTCAAGTGGTGGTCGCTATTATTGAGCCTAAAACGTCC"),
                ("seq2", "CCTAAAACGTCCGTAGTCGGCTTTGTAAATCCCTGGGTAAATCGGGT"),
                ("seq3", "TCGCTATTATTGAGCCTAAAACGTCCGTAGTCGGCTTTGTAAATCCC"),
                ("seq4", "TACCCGCAGCTCAAGTGGTGGTCGCTATTATTGAGCCTAAAACGTCC"),
                ("seq5", "CTAAAACGTCCGTAGTCGGCTTTGTAAATCCCTGGGTAAATAGGGTC"),
                ("seq6", "TTGAGCCTAAAACGTCCGTAGTCGGCTTTGTAAATCCCTGGGTAAAT"),
                ("phix1", "TCTAAAGGTAAAAAACGTTCTGGCGCTCGCCCTGGTCGTCCGCAGCC"),
                ("phix2", "CTGGCGCTCGCCCTGGTCGTCCGCAGCCGTTGCGAGGTACTAAAGGC"),
                ("phix3", "GCGCATAAATTTGAGCAGATTTGTCGTCACAGGTTGCGCCGCCAAAA")]
        exp_seqs = ["seq1", "seq2", "seq3", "seq4", "seq5", "seq6"]
        seqs_fp = join(self.working_dir, "seqs.fasta")
        with open(seqs_fp, 'w') as seqs_f:
            for seq in seqs:
                seqs_f.write(">%s\n%s\n" % seq)
        ref = [("ref1", "TACCCGCAGCTCAAGTGGTGGTCGCTATTATTGAGCCTAAAACGTCCGTA"
                        "GTCGGCTTTGTAAATCCCTGGGTAAATCGGGT"),
               ("ref2", "TACCCGCAGCTCAAGTGGTGGTCGCTATTATTGAGCCTAAAACGTCCGTAG"
                        "TCGGCTTTGTAAATCCCTGGGTAAATCGGGT"),
               ("ref3", "TACCCGCAGCTCAAGTGGTGGTCGCTATTATTGAGCCTAAAACGTCCGTAG"
                        "TCGGCTTTGTAAATCCCTGGGTAAATCGGGT"),
               ("ref4", "TACCCGCAGCTCAAGTGGTGGTCGCTATTATTGAGCCTAAAACGTCCGTAG"
                        "TCGGCTTTGTAAATCCCTGGGTAAATCGGGT"),
               ("ref5", "TACCCGCAGCTCAAGTGGTGGTCGCTATTATTGAGCCTAAAACGTCCGTAG"
                        "TCGGCTTTGTAAATCCCTGGGTAAATAGGGT"),
               ("ref6", "TACCCGCAGCTCAAGTGGTGGTCGCTATTATTGAGCCTAAAACGTCCGTAG"
                        "TCGGCTTTGTAAATCCCTGGGTAAATCGGGT")]
        ref_fp = join(self.working_dir, "ref2.fasta")
        with open(ref_fp, 'w') as ref_f:
            for seq in ref:
                ref_f.write(">%s\n%s\n" % seq)
        self.files_to_remove.append(ref_fp)
        ref_db_fp = build_index_sortmerna(
            ref_fp=(ref_fp,),
            working_dir=self.working_dir)
        output_fp = remove_artifacts_seqs(seqs_fp=seqs_fp,
                                          ref_fp=(ref_fp,),
                                          working_dir=self.working_dir,
                                          ref_db_fp=ref_db_fp,
                                          negate=False,
                                          threads=1)
        obs_seqs = []
        with open(output_fp, 'U') as output_f:
            for label, seq in parse_fasta(output_f):
                obs_seqs.append(label)
        self.assertEqual(obs_seqs, exp_seqs)

    def test_remove_artifacts_seqs_index_prebuilt(self):
        """ Test remove_artifacts_seqs() function for removing
            sequences not matching to a reference database
            using SortMeRNA. This test passes a built index.
        """
        seqs = [("seq1", "TACCCGCAGCTCAAGTGGTGGTCGCTATTATTGAGCCTAAAACGTCC"),
                ("seq2", "CCTAAAACGTCCGTAGTCGGCTTTGTAAATCCCTGGGTAAATCGGGT"),
                ("seq3", "TCGCTATTATTGAGCCTAAAACGTCCGTAGTCGGCTTTGTAAATCCC"),
                ("seq4", "TACCCGCAGCTCAAGTGGTGGTCGCTATTATTGAGCCTAAAACGTCC"),
                ("seq5", "CTAAAACGTCCGTAGTCGGCTTTGTAAATCCCTGGGTAAATAGGGTC"),
                ("seq6", "TTGAGCCTAAAACGTCCGTAGTCGGCTTTGTAAATCCCTGGGTAAAT"),
                ("phix1", "TCTAAAGGTAAAAAACGTTCTGGCGCTCGCCCTGGTCGTCCGCAGCC"),
                ("phix2", "CTGGCGCTCGCCCTGGTCGTCCGCAGCCGTTGCGAGGTACTAAAGGC"),
                ("phix3", "GCGCATAAATTTGAGCAGATTTGTCGTCACAGGTTGCGCCGCCAAAA")]
        exp_seqs = ["seq1", "seq2", "seq3", "seq4", "seq5", "seq6"]
        seqs_fp = join(self.working_dir, "seqs.fasta")
        with open(seqs_fp, 'w') as seqs_f:
            for seq in seqs:
                seqs_f.write(">%s\n%s\n" % seq)
        ref = [("ref1", "TACCCGCAGCTCAAGTGGTGGTCGCTATTATTGAGCCTAAAACGTCCGTA"
                        "GTCGGCTTTGTAAATCCCTGGGTAAATCGGGT"),
               ("ref2", "TACCCGCAGCTCAAGTGGTGGTCGCTATTATTGAGCCTAAAACGTCCGTAG"
                        "TCGGCTTTGTAAATCCCTGGGTAAATCGGGT"),
               ("ref3", "TACCCGCAGCTCAAGTGGTGGTCGCTATTATTGAGCCTAAAACGTCCGTAG"
                        "TCGGCTTTGTAAATCCCTGGGTAAATCGGGT"),
               ("ref4", "TACCCGCAGCTCAAGTGGTGGTCGCTATTATTGAGCCTAAAACGTCCGTAG"
                        "TCGGCTTTGTAAATCCCTGGGTAAATCGGGT"),
               ("ref5", "TACCCGCAGCTCAAGTGGTGGTCGCTATTATTGAGCCTAAAACGTCCGTAG"
                        "TCGGCTTTGTAAATCCCTGGGTAAATAGGGT"),
               ("ref6", "TACCCGCAGCTCAAGTGGTGGTCGCTATTATTGAGCCTAAAACGTCCGTAG"
                        "TCGGCTTTGTAAATCCCTGGGTAAATCGGGT")]
        ref_fp = join(self.working_dir, "ref3.fasta")
        with open(ref_fp, 'w') as ref_f:
            for seq in ref:
                ref_f.write(">%s\n%s\n" % seq)
        self.files_to_remove.append(ref_fp)
        # build index
        sortmerna_db = build_index_sortmerna([ref_fp], self.working_dir)
        output_fp = join(self.working_dir, "seqs_filtered.fasta")
        output_fp = remove_artifacts_seqs(seqs_fp=seqs_fp,
                                          ref_fp=(ref_fp,),
                                          working_dir=self.working_dir,
                                          ref_db_fp=sortmerna_db,
                                          negate=False,
                                          threads=1)

        obs_seqs = []
        with open(output_fp, 'U') as output_f:
            for label, seq in parse_fasta(output_f):
                obs_seqs.append(label)
        self.assertEqual(obs_seqs, exp_seqs)

    def test_remove_artifacts_seqs_negate(self):
        """ Test remove_artifacts_seqs() function for removing
            sequences matching to a reference database
            using SortMeRNA (negate option).
        """
        seqs = [("seq1", "TACCCGCAGCTCAAGTGGTGGTCGCTATTATTGAGCCTAAAACGTCC"),
                ("seq2", "CCTAAAACGTCCGTAGTCGGCTTTGTAAATCCCTGGGTAAATCGGGT"),
                ("seq3", "TCGCTATTATTGAGCCTAAAACGTCCGTAGTCGGCTTTGTAAATCCC"),
                ("seq4", "TACCCGCAGCTCAAGTGGTGGTCGCTATTATTGAGCCTAAAACGTCC"),
                ("seq5", "CTAAAACGTCCGTAGTCGGCTTTGTAAATCCCTGGGTAAATAGGGTC"),
                ("seq6", "TTGAGCCTAAAACGTCCGTAGTCGGCTTTGTAAATCCCTGGGTAAAT"),
                ("phix1", "TCTAAAGGTAAAAAACGTTCTGGCGCTCGCCCTGGTCGTCCGCAGCC"),
                ("phix2", "CTGGCGCTCGCCCTGGTCGTCCGCAGCCGTTGCGAGGTACTAAAGGC"),
                ("phix3", "GCGCATAAATTTGAGCAGATTTGTCGTCACAGGTTGCGCCGCCAAAA")]
        # seq5 is 80% similar, so should be kept for 0.95 default similarity
        # to artifacts
        exp_seqs = ["seq5", "phix1", "phix2", "phix3"]
        seqs_fp = join(self.working_dir, "seqs.fasta")
        with open(seqs_fp, 'w') as seqs_f:
            for seq in seqs:
                seqs_f.write(">%s\n%s\n" % seq)
        ref = [("ref1", "TACCCGCAGCTCAAGTGGTGGTCGCTATTATTGAGCCTAAAACGTCCGTA"
                        "GTCGGCTTTGTAAATCCCTGGGTAAATCGGGT"),
               ("ref2", "TACCCGCAGCTCAAGTGGTGGTCGCTATTATTGAGCCTAAAACGTCCGTAG"
                        "TCGGCTTTGTAAATCCCTGGGTAAATCGGGT"),
               ("ref3", "TACCCGCAGCTCAAGTGGTGGTCGCTATTATTGAGCCTAAAACGTCCGTAG"
                        "TCGGCTTTGTAAATCCCTGGGTAAATCGGGT"),
               ("ref4", "TACCCGCAGCTCAAGTGGTGGTCGCTATTATTGAGCCTAAAACGTCCGTAG"
                        "TCGGCTTTGTAAATCCCTGGGTAAATCGGGT"),
               ("ref5", "TACCCGCAGCTCAAGTGGTGGTCGCTATTATTGAGCCTAAAACGTCCGTAG"
                        "TCGGCTTTGTAAATCCCTGGGTAAATAGGGT"),
               ("ref6", "TACCCGCAGCTCAAGTGGTGGTCGCTATTATTGAGCCTAAAACGTCCGTAG"
                        "TCGGCTTTGTAAATCCCTGGGTAAATCGGGT")]
        ref_fp = join(self.working_dir, "ref4.fasta")
        with open(ref_fp, 'w') as ref_f:
            for seq in ref:
                ref_f.write(">%s\n%s\n" % seq)
        self.files_to_remove.append(ref_fp)
        ref_db_fp = build_index_sortmerna([ref_fp], self.working_dir)
        output_fp = join(self.working_dir, "seqs_filtered.fasta")
        output_fp = remove_artifacts_seqs(seqs_fp=seqs_fp,
                                          ref_fp=(ref_fp,),
                                          working_dir=self.working_dir,
                                          ref_db_fp=ref_db_fp,
                                          negate=True,
                                          threads=1)
        obs_seqs = []
        with open(output_fp, 'U') as output_f:
            for label, seq in parse_fasta(output_f):
                obs_seqs.append(label)
        self.assertEqual(obs_seqs, exp_seqs)

    def test_remove_chimeras_denovo_from_seqs(self):
        """ Test remove_chimeras_denovo_from_seqs() method functionality.
            Remove chimeric sequences from a FASTA file using the UCHIME
            algorithm, implemented in VSEARCH.
        """
        seqs = [("s1_104;size=2;", "GTGCCAGCCGCCGCGGTAATACCCGCAGCTCAAGTGGTG"
                                   "GTCGCTATTATTGAGCCTAAAACGTCCGTAGTCGGCTTT"
                                   "GTAAATCCCTGGGTAAATCGGGAAGCTTAACTTTCCGAC"
                                   "TTCCGAGGAGACTGTCAAACTTGGGACCGGGAG"),
                ("s1_106;size=2;", "GTGTCAGCCGCCGCGGTAATACCAGCTCTCCGAGTGGTG"
                                   "TGGATGTTTATTGGGCCTAAAGCGTCCGTAGCCGGCTGC"
                                   "GCAAGTCTGTCGGGAAATCCGCACGCCTAACGTGCGGGC"
                                   "GTCCGGCGGAAACTGCGTGGCTTGGGACCGGAA"),
                ("s1_1;size=9;", "TACCCGCAGCTCAAGTGGTGGTCGCTATTATTGAGCCTAAA"
                                 "ACGTCCGTAGTCGGCTTTGTAAATCCCTGGGTAAATCGGGT"
                                 "CGCTTAACGATCCGATTCTGGGGAGACTGCAAAGCTTGGGA"
                                 "CCGGGCGAGGTTAGAGGTACTCTCGGG"),
                ("s1_20;size=9;", "TACCTGCAGCCCAAGTGGTGGTCGATTTTATTGAGTCTAA"
                                  "AACGTTCGTAGCCGGTTTGATAAATCCTTGGGTAAATCGG"
                                  "GAAGCTTAACTTTCCGATTCCGAGGAGACTGTCAAACTTG"
                                  "GGACCGGGAGAGGCTAGAGGTACTTCTGGG"),
                ("s1_40;size=8;", "TACCAGCTCTCCGAGTGGTGTGGATGTTTATTGGGCCTAA"
                                  "AGCATCCGTAGCTGGCTAGGTTAGTCCCCTGTTAAATCCA"
                                  "CCGAATTAATCGTTGGATGCGGGGGATACTGCTTGGCTAG"
                                  "GGGACGAGAGAGGCAGACGGTATTTCCGGG"),
                ("s1_60;size=8;", "TACCGGCAGCTCAAGTGATGACCGCTATTATTGGGCCTAA"
                                  "AGCGTCCGTAGCCGGCTGCGCAAGTCTGTCGGGAAATCCG"
                                  "CACGCCTAACGTGCGGGTCCGGCGGAAACTGCGTGGCTTG"
                                  "GGACCGGAAGACTCGAGGGGTACGTCAGGG")]
        seqs_non_chimera = ["s1_1;size=9;", "s1_20;size=9;",
                            "s1_40;size=8;", "s1_60;size=8;"]
        seqs_fp = join(self.working_dir, "seqs.fasta")
        with open(seqs_fp, 'w') as seqs_f:
            for seq in seqs:
                seqs_f.write(">%s\n%s\n" % seq)
        output_fp = remove_chimeras_denovo_from_seqs(
            seqs_fp=seqs_fp,
            working_dir=self.working_dir)
        seqs_obs = []
        with open(output_fp, 'U') as output_f:
            for label, seq in parse_fasta(output_f):
                label = label.split()[0]
                seqs_obs.append(label)
        self.assertEqual(seqs_non_chimera, seqs_obs)

    def test_multiple_sequence_alignment(self):
        """Test multiple sequence alignment.
        """
        seqs = [DNA('caccggcggcccggtggtggccattattattgggtctaaag', id='seq_1'),
                DNA('caccggcggcccgagtggtggccattattattgggtcaagg', id='seq_2'),
                DNA('caccggcggcccgagtgatggccattattattgggtctaaag', id='seq_3'),
                DNA('aaccggcggcccaagtggtggccattattattgggtctaaag', id='seq_4'),
                DNA('caccgggcccgagtggtggccattattattgggtctaaag', id='seq_5')]
        seqs_col = SequenceCollection(seqs)
        seqs_fp = join(self.working_dir, "seqs.fna")
        with open(seqs_fp, 'w') as o:
            o.write(seqs_col.to_fasta())
        alignment_file = multiple_sequence_alignment(seqs_fp)
        with open(alignment_file, 'U') as f:
            aligned_seqs = [DNA(item[1], id=item[0])
                            for item in parse_fasta(f)]

        align_exp = [
            DNA(
                'caccggcggcccg-gtggtggccattattattgggtctaaag', id='seq_1'),
            DNA(
                'caccggcggcccgagtggtggccattattattgggtcaagg-', id='seq_2'),
            DNA(
                'caccggcggcccgagtgatggccattattattgggtctaaag', id='seq_3'),
            DNA(
                'aaccggcggcccaagtggtggccattattattgggtctaaag', id='seq_4'),
            DNA(
                'caccg--ggcccgagtggtggccattattattgggtctaaag', id='seq_5')]
        self.assertEqual(aligned_seqs, align_exp)

    def test_build_index_sortmerna(self):
        """Test functionality of build_index_sortmerna()
        """
        ref1 = [("ref1", "TACCCGCAGCTCAAGTGGTGGTCGCTATTATTGAGCCTAAAACGTCCGTA"
                 "GTCGGCTTTGTAAATCCCTGGGTAAATCGGGT"),
                ("ref2", "TACCCGCAGCTCAAGTGGTGGTCGCTATTATTGAGCCTAAAACGTCCGTAG"
                 "TCGGCTTTGTAAATCCCTGGGTAAATCGGGT"),
                ("ref3", "TACCCGCAGCTCAAGTGGTGGTCGCTATTATTGAGCCTAAAACGTCCGTAG"
                 "TCGGCTTTGTAAATCCCTGGGTAAATCGGGT"),
                ("ref4", "TACCCGCAGCTCAAGTGGTGGTCGCTATTATTGAGCCTAAAACGTCCGTAG"
                 "TCGGCTTTGTAAATCCCTGGGTAAATCGGGT"),
                ("ref5", "TACCCGCAGCTCAAGTGGTGGTCGCTATTATTGAGCCTAAAACGTCCGTAG"
                 "TCGGCTTTGTAAATCCCTGGGTAAATAGGGT"),
                ("ref6", "TACCCGCAGCTCAAGTGGTGGTCGCTATTATTGAGCCTAAAACGTCCGTAG"
                 "TCGGCTTTGTAAATCCCTGGGTAAATCGGGT")]
        ref2 = [("ref1", "GTCGTAGCTAGCTGCCCACGATCGTAGCTAGCTAGCTACGTAGCTCATCAC"
                 "TCGCCGACCCACGTCCCACTGATGCTGTGGG"),
                ("ref2", "GCGGCGCCCAAAAATGTCGTGTAAAATTTTCTCGTACCCACTTGCTACCCA"
                 "TGGCCGCCATGCTGCTAACGCAATATATATA"),
                ("ref3", "TGTGAAAGCGCGCGAGAGAGTCGTATATATGGGCGCGGCGCGATGCTGCCC"
                 "GTCGATGCTGATCCCCCACGTACGTAGCCCC"),
                ("ref4", "GTGTGCTCGCGTAGCTAGCTTATATATCGGCGCGTAGTGCTAGCCCCAAAA"
                 "GTGTCCCCCCCCTCCTTTTTTATATATGCAA"),
                ("ref5", "TACCCGCAGCTCAAGTGGTGGTCGCTATTATTGAGCCTAAAACGTCCGTAG"
                 "TCGGCTTTGTAAATCCCTGGGTAAATAGGGT"),
                ("ref6", "TACCCGCAGCTCAAGTGGTGGTCGCTATTATTGAGCCTAAAACGTCCGTAG"
                 "TCGGCTTTGTAAATCCCTGGGTAAATCGGGT")]
        ref1_fp = join(self.working_dir, "ref1.fasta")
        with open(ref1_fp, 'w') as ref_f:
            for seq in ref1:
                ref_f.write(">%s\n%s\n" % seq)
        ref2_fp = join(self.working_dir, "ref2.fasta")
        with open(ref2_fp, 'w') as ref_f:
            for seq in ref2:
                ref_f.write(">%s\n%s\n" % seq)
        ref_fps = tuple([ref1_fp, ref2_fp])
        ref_db_fp = build_index_sortmerna(
            ref_fp=ref_fps,
            working_dir=self.working_dir)
        self.assertEqual(len(ref_fps), len(ref_db_fp))

    def run_workflow_try(self, simfilename, origfilename, ref_fp, ref_db_fp):
        """Test launching the complete workflow using simulated sequences
        and compare to original ground truth.

        Parameters
        ----------
        simfilename : str
            name of the simulated reads fasta file
        origfilename : str
            name of the fasta file with the ground truth sequences
        """
        seqs_fp = simfilename
        output_fp = self.working_dir
        mean_error = 0.005
        error_dist = [1, 0.05, 0.000005, 0.000005, 0.000005, 0.000005,
                      0.0000025, 0.0000025, 0.0000025, 0.0000025, 0.0000025,
                      0.0000005, 0.0000005, 0.0000005, 0.0000005]
        indel_prob = 0.01
        indel_max = 3
        trim_length = 100
        min_size = 2
        negate = False
        threads = 1
        nochimera = launch_workflow(seqs_fp=seqs_fp, working_dir=output_fp,
                                    mean_error=mean_error,
                                    error_dist=error_dist,
                                    indel_prob=indel_prob,
                                    indel_max=indel_max,
                                    trim_length=trim_length,
                                    min_size=min_size,
                                    ref_fp=(ref_fp,),
                                    ref_db_fp=ref_db_fp,
                                    negate=negate,
                                    threads_per_sample=threads)

        # get the trimmed ground truth sequences
        with open(origfilename, 'U') as f:
            orig_seqs = [item[1] for item in parse_fasta(f)]
        orig_seqs = [item[:trim_length].upper() for item in orig_seqs]

        output_filename = 'final.biom'
        output_table_fp = join(output_fp, output_filename)

        create_otu_table(output_table_fp, [(nochimera, seqs_fp)])

        table_obs = load_table(output_table_fp)
        outseqs = table_obs.ids(axis='observation')
        outseqs = list(outseqs)
        outseqs.sort()
        orig_seqs.sort()

        # test we see all ground truth sequences and no other
        self.assertEqual(outseqs, orig_seqs)

    def test_get_files_for_table(self):
        filelist = get_files_for_table(self.test_data_dir)
        file1 = join(self.test_data_dir,
                     'testmerge.fasta.trim.derep.no_artifacts'
                     '.msa.deblur.no_chimeras')
        file2 = join(self.test_data_dir,
                     'testmerge2.fasta.trim.derep.no_artifacts'
                     '.msa.deblur.no_chimeras')
        self.assertEqual(len(filelist), 2)
        self.assertTrue(file1 in [filelist[0][0], filelist[1][0]])
        self.assertTrue(file2 in [filelist[0][0], filelist[1][0]])
        self.assertTrue('testmerge' in [filelist[0][1], filelist[1][1]])

    def test_create_otu_table(self):
        # merge the fasta files
        m1 = join(self.test_data_dir,
                  'testmerge.fasta.trim.derep.no_artifacts'
                  '.msa.deblur.no_chimeras')
        m2 = join(self.test_data_dir,
                  'testmerge2.fasta.trim.derep.no_artifacts'
                  '.msa.deblur.no_chimeras')
        outfile = join(self.working_dir, 'testmerge.biom')
        create_otu_table(outfile, [(m1, 'testmerge'), (m2, 'testmerge2')])

        # test the result
        table = load_table(outfile)

        # test a sequence present in both
        self.assertEqual(table.get_value_by_ids(
            'TACGAGGggggCGAGCGTTGTTCGGAATTATTGGGCGTAAAAGGTGCGTAGGCGGTTCG'
            'GTAAGTTTCGTGTGAAATCTTCGGGCTCAACTCGAAGCCTGCACGAAATACTGCCGGGC'
            'TTGAGTGTGGGAGAGGTGAGTGGAATTTCCGGT', 'testmerge'), 5)
        self.assertEqual(table.get_value_by_ids(
            'TACGAGGggggCGAGCGTTGTTCG'
            'GAATTATTGGGCGTAAAAGGTGCGTAGGCGGTTCGGTAAGTTTCGTGTGAAATCTTCGGG'
            'CTCAACTCGAAGCCTGCACGAAATACTGCCGGGCTTGAGTGTGGGAGAGGTGAGTGGAAT'
            'TTCCGGT', 'testmerge2'), 8)
        # and an otu present only in one
        self.assertEqual(table.get_value_by_ids(
            'TACGTAGGTGGCAAGCGTTATCCGGAATTATTGGGCGTAAAGCGAGCGTAGGCGGTTTCTT'
            'AAGTCTGATGTGAAAGCCCACGGCTCAACCGTGGAGGGTCATTGGAAACTGGGGAACTTGA'
            'GTGCAGAAGAGGAGAGTGGAATTCCATGT', 'testmerge'), 7)
        self.assertEqual(table.get_value_by_ids(
            'TACGTAGGTGGCAAGCGTTATCCGGAATTATTGGGCGTAAAGCGAGCGTAGGCGGTTTCTTA'
            'AGTCTGATGTGAAAGCCCACGGCTCAACCGTGGAGGGTCATTGGAAACTGGGGAACTTGAGT'
            'GCAGAAGAGGAGAGTGGAATTCCATGT', 'testmerge2'), 0)

    def test_launch_workflow(self):
        """Test launching complete workflow using 3 simulated sequence files.
        seqs1 - 100 reads using art, original sequences are >0.5 identical.
        seqs2 - 200 reads using grinder, original sequences are >0.9 identical,
        0.1 chimeras, 35 phix reads
        seqs3 - simple - 15 reads from seqs1 (10 reads for 1001203,
        5 reads for 694276) for manual test validation
        """
        # index the 70% rep. set database
        ref_fp = join(self.test_data_dir, '70_otus.fasta')
        ref_db_fp = build_index_sortmerna(
            ref_fp=(ref_fp,),
            working_dir=self.working_dir)

        self.run_workflow_try(self.seqs_s1_fp,
                              self.orig_s1_fp, ref_fp, ref_db_fp)
        self.run_workflow_try(self.seqs_s2_fp,
                              self.orig_s2_fp, ref_fp, ref_db_fp)
        self.run_workflow_try(self.seqs_s3_fp,
                              self.orig_s3_fp, ref_fp, ref_db_fp)

    def get_seqs_act_split_sequence_on_sample_ids(self, output_dir):
        """Parse output of split_sequence_file_on_sample_ids_to_files()

        Parameters
        ----------
        output_dir: string
            output directory path storing FASTA files

        Returns
        -------
        seqs_act: dict
            dictionary with keys being sample IDs and values list of
            sequences belonging to sample ID
        """
        seqs_act = {}
        for fn in listdir(output_dir):
            input_fp = join(output_dir, fn)
            sample_file = splitext(fn)[0]
            with open(input_fp, 'U') as input_f:
                for label, seq in parse_fasta(input_f):
                    sample = label.split('_')[0]
                    self.assertEqual(sample_file, sample)
                    if sample not in seqs_act:
                        seqs_act[sample] = [(label, seq)]
                    else:
                        seqs_act[sample].append((label, seq))
        return seqs_act

    def test_sample_id_from_read_id(self):
        """Test the fasta readid to sample id
        used in split_sequence_file_on_sample_ids_to_files
        """
        self.assertEqual(sample_id_from_read_id("Samp1_0 M04771:27:000000000"
                                                "-ARFWH:1:1101:18081:1897 1:"
                                                "N:0:0 orig_bc=CGTTAAGTCAGC n"
                                                "ew_bc=CGTTAAGTCAGC bc_diffs="
                                                "0"), "Samp1")
        self.assertEqual(sample_id_from_read_id("S1_1_0 M04771:27:000000000"
                                                "-ARFWH:1:1101:18081:1897 1:"
                                                "N:0:0 orig_bc=CGTTAAGTCAGC n"
                                                "ew_bc=CGTTAAGTCAGC bc_diffs="
                                                "0"), "S1_1")

    def test_split_sequence_file_on_sample_ids_to_files(self):
        """Test functionality of split_sequence_file_on_sample_ids_to_files()
        """
        seqs_fasta = {"s1": [
                      ("s1_seq1",
                       "TACCGGCAGCTCAAGTGATGACCGCTATTATTGGGCCTAAAGCGTCCG"),
                      ("s1_seq2",
                       "TACCGGCAGCTCAAGTGATGACCGCTATTATTGGGCCTAAAGCGTCCG")],
                      "s2": [
                      ("s2_seq3",
                       "TACCGGCAGCTCAAGTGATGACCGCTATTATTGGGCCTAAAGCGTCCG"),
                      ("s2_seq4",
                       "TACCGGCAGCTCAAGTGATGACCGCTATTATTGGGCCTAAAGCGTCCT")],
                      "s3": [
                      ("s3_seq5",
                       "TACCAGCCCCTTAAGTGGTAGGGACGATTATTTGGCCTAAAGCGTCCG"),
                      ("s3_seq6",
                       "CTGCAAGGCTAGGGGGCGGGAGAGGCGGGTGGTACTTGAGGGGAGAAT")],
                      "s4": [
                      ("s4_seq7",
                       "CTGCAAGGCTAGGGGGCGGGAGAGGCGGGTGGTACTTGAGGGGAGAAT")]}
        # Test FASTA file split on sample IDs to multiple FASTA files
        seqs_fp = join(self.working_dir, "seqs.fasta")
        with open(seqs_fp, 'w') as seqs_f:
            for sample in seqs_fasta:
                for seq in seqs_fasta[sample]:
                    seqs_f.write(">%s\n%s\n" % seq)
        output_dir = mkdtemp()
        with open(seqs_fp, 'U') as seqs_f:
            split_sequence_file_on_sample_ids_to_files(seqs=seqs_f,
                                                       outdir=output_dir)
        seqs_act = self.get_seqs_act_split_sequence_on_sample_ids(
            output_dir=output_dir)
        self.assertEqual(seqs_fasta, seqs_act)


if __name__ == '__main__':
    main()
