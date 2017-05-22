# -*- encoding: utf-8 -*-
__author__ = 'tla'

import json
import os
import unittest
import sys

import yaml

from tpen2tei.parse import from_sc
import tpen2tei.wordtokenize as wordtokenize
from config import config as config


class Test (unittest.TestCase):

    # Our default (and example) list of special characters that might occur as
    # glyph (<g/>) elements. A true list should be passed to the from_sc call.
    # The key is the normalized form; the tuple is (xml:id, description).
    _armenian_glyphs = {
        'աշխարհ': ('asxarh', 'ARMENIAN ASHXARH SYMBOL'),
        'ամենայն': ('amenayn', 'ARMENIAN AMENAYN SYMBOL'),
        'որպէս': ('orpes', 'ARMENIAN ORPES SYMBOL'),
        'երկիր': ('erkir', 'ARMENIAN ERKIR SYMBOL'),
        'երկին': ('erkin', 'ARMENIAN ERKIN SYMBOL'),
        'ընդ': ('und', 'ARMENIAN END SYMBOL'),
        'ըստ': ('ust', 'ARMENIAN EST SYMBOL'),
        'պտ': ('ptlig', 'ARMENIAN PEH-TIWN LIGATURE'),
        'թե': ('techlig', 'ARMENIAN TO-ECH LIGATURE'),
        'թի': ('tinilig', 'ARMENIAN TO-INI LIGATURE'),
        'թէ': ('tehlig', 'ARMENIAN TO-EH LIGATURE'),
        'էս': ('eslig', 'ARMENIAN EH-SEH LIGATURE'),
        'ես': ('echslig', 'ARMENIAN ECH-SEH LIGATURE'),
        'յր': ('yrlig', 'ARMENIAN YI-REH LIGATURE'),
        'զմ': ('zmlig', 'ARMENIAN ZA-MEN LIGATURE'),
        'թգ': ('tglig', 'ARMENIAN TO-GIM LIGATURE'),
        'ա': ('avar', 'ARMENIAN AYB VARIANT'),
        'հ': ('hvar', 'ARMENIAN HO VARIANT'),
        'յ': ('yabove', 'ARMENIAN YI SUPERSCRIPT VARIANT')
    }

    testdoc = None

    def setUp(self):
        self.settings = config()

        self.tei_ns = self.settings['namespaces']['tei']
        self.xml_ns = self.settings['namespaces']['xml']

        # self.ns_id = '{{{:s}}}id'.format(self.xml_ns)
        # self.ns_lb = '{{{:s}}}lb'.format(self.tei_ns)
        # self.ns_note = '{{{:s}}}note'.format(self.tei_ns)
        # self.ns_pb = "{{{:s}}}pb".format(self.tei_ns)
        # self.ns_text = '{{{:s}}}text'.format(self.tei_ns)

        self.testfiles = self.settings['testfiles']
        msdata = load_JSON_file(self.testfiles['json'])
        self.testdoc = from_sc(msdata)
        self.testdoc_special = from_sc(msdata, special_chars=self._armenian_glyphs)

    # def setUp(self):
    #     with open('./data/M1731.json', encoding='utf-8') as fh:
    #         jdata = json.load(fh)
    #     self.testdoc = from_sc(jdata)

    def test_simple(self):
        """Test a plain & simple file without special markup beyond line breaks."""
        pass

    def test_glyphs(self):
        """Test the correct detection and rendering of glyphs. The characters in
        the resulting token should be the characters that are the content of the
        g tag. """
        testdata = {'յեգի<g xmlns="http://www.tei-c.org/ns/1.0" ref="#&#x57A;&#x57F;"/>ոս': 'յեգիոս',
                    'յ<g xmlns="http://www.tei-c.org/ns/1.0" ref="&#x561;&#x577;&#x56D;&#x561;&#x580;&#x570;">աշխար</g>հն': 'յաշխարհն',
                    '<g xmlns="http://www.tei-c.org/ns/1.0" ref="">աշխարհ</g>ին': 'աշխարհին',
                    'ար<g xmlns="http://www.tei-c.org/ns/1.0" ref="">ա</g>պ<lb xmlns="http://www.tei-c.org/ns/1.0" xml:id="l101276841" n="14"/>կաց': 'արապկաց',
                    '<g xmlns="http://www.tei-c.org/ns/1.0" ref="">աշխարհ</g>ն': 'աշխարհն'}

        testdata_special = {'յեգի<g xmlns="http://www.tei-c.org/ns/1.0" ref="#ptlig">պտ</g>ոս': {'token': 'յեգիպտոս', 'occurrence': 1},
                            'յ<g xmlns="http://www.tei-c.org/ns/1.0" ref="#asxarh">աշխար</g>հն': {'token': 'յաշխարհն', 'occurrence': 1},
                            '<g xmlns="http://www.tei-c.org/ns/1.0" ref="#asxarh">աշխարհ</g>ին': {'token': 'աշխարհին', 'occurrence': 2},
                            'ար<g xmlns="http://www.tei-c.org/ns/1.0" ref="#avar">ա</g>պ<lb xmlns="http://www.tei-c.org/ns/1.0" xml:id="l101276841" n="14"/>կաց': {'token': 'արապկաց', 'occurrence': 1},
                            '<g xmlns="http://www.tei-c.org/ns/1.0" ref="#asxarh">աշխարհ</g>ն': {'token': 'աշխարհն', 'occurrence': 1}}

        tokens = wordtokenize.from_etree(self.testdoc)
        # Find the token that has our substitution
        for t in tokens:
            if '<g xmlns="http://www.tei-c.org/ns/1.0" ref="' in t['lit']:
                self.assertIsNotNone(testdata.get(t['lit']), "Error in rendering glyphs (input data not covered by testdata)")
                self.assertTrue(t['t'] == testdata.get(t['lit']), "Error in rendering glyphs")
                del testdata[t['lit']]
        self.assertEqual(len(testdata), 0, "Did not find any test token")

        tokens = wordtokenize.from_etree(self.testdoc_special)
        # Find the token that has our substitution
        for t in tokens:
            if '<g xmlns="http://www.tei-c.org/ns/1.0" ref="' in t['lit']:
                self.assertIsNotNone(testdata_special.get(t['lit']), "Error in rendering glyphs (input data not covered by testdata)")
                self.assertTrue(t['t'] == testdata_special.get(t['lit'])['token'], "Error in rendering glyphs")
                testdata_special[t['lit']]['occurrence'] -= 1
                if testdata_special[t['lit']]['occurrence'] == 0:
                    del testdata_special[t['lit']]
        self.assertEqual(len(testdata_special), 0, "Did not find any test token")

    def test_substitution(self):
        """Test that the correct words are picked out of a subst tag."""
        tokens = wordtokenize.from_etree(self.testdoc)
        # Find the token that has our substitution
        for t in tokens:
            if t['lit'] != 'դե<add xmlns="http://www.tei-c.org/ns/1.0">ռ</add>ևս':
                continue
            self.assertEqual(t['t'], 'դեռևս')
            break
        else:
            self.assertTrue(False, "Did not find the testing token")

    def test_substitution_layer(self):
        """Test that the first_layer option works correctly."""
        tokens = wordtokenize.from_etree(self.testdoc, first_layer=True)
        # Find the token that has our substitution
        for t in tokens:
            if t['lit'] != 'դե<del xmlns="http://www.tei-c.org/ns/1.0">ղ</del>ևս':
                continue
            self.assertEqual(t['t'], 'դեղևս')
            break
        else:
            self.assertTrue(False, "Did not find the testing token")

    def test_del_word_boundary(self):
        """Test that a strategically placed del doesn't cause erroneous joining of words.
        TODO add testing data"""
        pass

    def test_gap(self):
        """Test that gaps are handled correctly. At the moment this means that no token
        should be generated for a gap."""
        pass

    def test_milestone_element(self):
        """Test that milestone elements (not <milestone>, but e.g. <lb/> or <cb/>)
         are passed through correctly in the token 'lit' field."""
        pass

    def test_milestone_option(self):
        """Test that passing a milestone option gives back only the text from the
        relevant <milestone/> element to the next one."""
        pass

    def test_arbitrary_element(self):
        """Test that arbitrary tags (e.g. <abbr>) are passed into 'lit' correctly."""
        pass

    def test_file_input(self):
        """Make sure we get a result when passing a file path."""
        pass

    def test_fh_input(self):
        """Make sure we get a result when passing an open filehandle object."""
        pass

    def test_string_input(self):
        """Make sure we get a result when passing a string containing XML."""
        pass

    def test_object_input(self):
        """Make sure we get a result when passing an lxml.etree object."""
        pass

    def testLegacyTokenization(self):
        """Test with legacy TEI files from 2009, to make sure the tokenizer
        works with them."""
        testfile = self.testfiles['tei_2009']
        with open(self.testfiles['tei_2009_reference'], encoding='utf-8') as rfh:
            rtext = rfh.read()

        reference = rtext.rstrip().split(' ')
        tokens = wordtokenize.from_file(testfile)
        for i, t in enumerate(tokens):
            self.assertEqual(t['t'], reference[i], "Mismatch at index %d: %s - %s" % (i, t, reference[i]))


def load_JSON_file(filename, encoding='utf-8'):
    data = ""
    try:
        with open(filename, encoding=encoding) as testfile:
            data = json.load(testfile)
        testfile.close()
    except FileNotFoundError:
        print("""File "{:s}" not found!""".format(filename))
    except ValueError:
        print("""File "{:s}" might not be a valid JSON file!""".format(filename))
    return data
