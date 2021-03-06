import unittest

from tpen2tei.parse import from_sc
from contextlib import redirect_stderr
from config import config as config
import helpers
import io

__author__ = 'tla'


class Test(unittest.TestCase):

    def setUp(self):
        settings = config()

        self.namespaces = settings['namespaces']
        self.tei_ns = settings['namespaces']['tei']
        self.xml_ns = settings['namespaces']['xml']

        self.glyphs = helpers.glyph_struct(settings['armenian_glyphs'])

        self.testfiles = settings['testfiles']
        msdata = helpers.load_JSON_file(self.testfiles['json'])
        self.testdoc = from_sc(
            msdata,
            special_chars=self.glyphs
        )

        user_defined = {'title': 'Ժամանակագրութիւն', 'author': 'Մատթէոս Ուռհայեցի'}
        legacydata = helpers.load_JSON_file(self.testfiles['legacy'])
        self.legacydoc = from_sc(legacydata, metadata=user_defined,
                                 special_chars=self.glyphs,
                                 numeric_parser=helpers.armenian_numbers,
                                 text_filter=helpers.tpen_filter)
        self.brokendata = helpers.load_JSON_file(self.testfiles['broken'])
        
    def ns(self, st):
        if st == 'id':
            return '{%s}id' % self.xml_ns
        else:
            return "{%s}%s" % (self.tei_ns, st)

    def test_basic(self):
        self.assertIsNotNone(self.testdoc.getroot())
        self.assertEqual(self.testdoc.getroot().tag, '{{{:s}}}TEI'.format(self.tei_ns))

    def test_blocks(self):
        """Test that the right block element is used in the right context."""
        root = self.testdoc.getroot()
        self.assertEqual(1, len(root.findall('.//%s//%s' % (self.ns('text'), self.ns('ab')))))
        self.assertEqual(0, len(root.findall('.//%s//%s' % (self.ns('text'), self.ns('p')))))
        d_json = helpers.load_JSON_file(self.testfiles['m3519'])
        d_root = from_sc(d_json, special_chars=self.glyphs, text_filter=helpers.tpen_filter)
        self.assertEqual(0, len(d_root.findall('.//%s/%s/%s' % (self.ns('text'), self.ns('body'), self.ns('ab')))))
        self.assertEqual(2, len(d_root.findall('.//%s/%s/%s' % (self.ns('text'), self.ns('body'), self.ns('p')))))

    def test_cert_correction(self):
        """Test that all numeric 'cert' values in a transcription are converted to one of high/medium/low."""
        cert_attributes = self.legacydoc.getroot().xpath('.//attribute::cert')
        self.assertEquals(len(cert_attributes), 32)
        cert_values = {'low': 11, 'medium': 20, 'high': 1}
        for attr in cert_attributes:
            self.assertIn(attr, ['high', 'medium', 'low'])
            cert_values[attr] -= 1
        for v in cert_values.values():
            self.assertEqual(v, 0)

    def test_columns(self):
        """Need to check that column transitions within the same page are
        detected and an appropriate XML element is inserted."""

        for lb_element in self.testdoc.getroot().iterfind(".//{:s}".format(self.ns('lb'))):
            n = lb_element.attrib.get('n')
            line_id = lb_element.attrib.get(self.ns('id'))
            if line_id == "l101276891" and n == "25":
                pb = False
                for sibling in lb_element.itersiblings():
                    if sibling.tag == "{{{:s}}}lb".format(self.tei_ns):
                        self.assertTrue(pb)
                        self.assertEqual(sibling.attrib.get('n'), "1", "Unexpected line")
                        self.assertEqual(sibling.attrib.get(self.ns('id')), "l101276826", "Unexpected line")
                        break
                    if sibling.tag == "{{{:s}}}pb".format(self.tei_ns):
                        self.assertEqual(sibling.attrib.get('n'), '75v')
                        pb = True
                else:
                    self.assertTrue(False, "Missing Pagebreak")
                break

    def test_comment(self):
        """Need to check that any TPEN annotations on a line get passed as
        <note> elements linked to the correct line in the @target attribute."""
        root = self.testdoc.getroot()
        text_part = root.find(self.ns('text'))
        self.assertIsNotNone(text_part)
        for tag in text_part.iterfind(".//{:s}".format(self.ns('note'))):
            target = tag.attrib.get('target')
            self.assertTrue(target and target == '#l101280110')

    # Correction code for the early conventions
    def test_correct_type_to_rend(self):
        """Test that the erroneous 'type' attribute on the 'del' element gets corrected to 'rend'"""
        dels = self.legacydoc.getroot().findall('.//{%s}del' % self.tei_ns)
        self.assertEqual(len(dels), 241)
        for d in dels:
            self.assertTrue('type' not in d)

    def test_correct_corr_to_subst(self):
        """Tests that the erroneous 'corr' elements were turned into 'subst' ones"""
        corrs = self.legacydoc.getroot().findall('.//{%s}corr' % self.tei_ns)
        substs = self.legacydoc.getroot().findall('.//{%s}subst' % self.tei_ns)
        self.assertEqual(len(corrs), 0)
        self.assertEqual(len(substs), 115)

    def test_facsimile(self):
        """Tests that facsimile information was added as expected."""
        testfacs = self.testdoc.getroot().find("./tei:facsimile", namespaces=self.namespaces)
        # There should be one facsimile element with two surfaces and N zones
        self.assertEqual(2, len(testfacs))
        for surface in testfacs:
            self.assertEqual('801', surface.get('lrx'))
            self.assertEqual('1000', surface.get('lry'))
            self.assertEqual(self.ns('graphic'), surface[0].tag)
            ulx = None
            lry = None
            for zone in surface[1:]:
                # Check that zone geometries look sane
                # The left x coordinate should not change in this document
                if ulx is None:
                    ulx = int(zone.get('ulx'))
                    self.assertTrue(ulx > 0)
                else:
                    self.assertEqual(ulx, int(zone.get('ulx')))
                # The upper y coordinate should be the same as the previous lower y
                if lry is None:
                    lry = int(zone.get('lry'))
                    self.assertTrue(lry > 0)
                else:
                    self.assertEqual(lry, int(zone.get('uly')))
                    lry = int(zone.get('lry'))
                # Each zone should have a corresponding line in the transcription
                zid = zone.get('{%s}id' % self.xml_ns)
                corr_line = self.testdoc.getroot().find(".//tei:lb[@facs='#%s']" % zid, namespaces=self.namespaces)
                self.assertIsNotNone(corr_line)
                self.assertEqual(zid.replace('z', 'l'), corr_line.get('{%s}id' % self.xml_ns))

    def test_filter(self):
        """Check that the text filter is producing the desired output in the transcription."""
        testlb = self.legacydoc.getroot().find(".//tei:lb[@xml:id='l100784691']",
                                               namespaces=self.namespaces)
        self.assertEqual(testlb.getnext().tag, self.ns('num'))
        self.assertEqual(testlb.getnext().tail, " վանք. և ե՛տ զայս ")
        self.assertEqual(testlb.getnext().getnext().tail, " գը֊\n")

    def test_functioning_namespace(self):
        """Just need to check that the XML document that gets returned has
        the correct namespace settings for arbitrary elements in the middle."""

        tei_ns = "{{{:s}}}".format(self.tei_ns)
        xml_ns = "{{{:s}}}".format(self.xml_ns)

        for element in self.testdoc.getroot().getiterator():
            self.assertEqual(element.nsmap, {None: '{:s}'.format(self.tei_ns)})
            for key in element.attrib.keys():
                if key.startswith('{'):
                    self.assertTrue(key.startswith(tei_ns) or key.startswith(xml_ns), 'Undefined Namespace')

    def test_glyph_correction(self):
        """Test that the various old ways glyphs got encoded in the transcription have the correct end result"""
        # աշխարհ: 134 + 6
        # թե: 114 + 10
        # թէ: 210 + 4
        # պտ: 320 + 18
        # ընդ: 57 + 9
        # որպէս: 17 + 2
        # Get the allowed glyphs
        glyphs = set(['#%s' % x.get('{%s}id' % self.xml_ns)
                      for x in self.legacydoc.getroot().findall('.//{%s}glyph' % self.tei_ns)])
        # Get all the 'g' elements and check that they have valid refs
        gs = self.legacydoc.getroot().findall('.//{%s}g' % self.tei_ns)
        for g in gs:
            self.assertIn(g.get('ref'), glyphs)

        expected = {'#asxarh': 140, '#techlig': 124, '#tehlig': 214, '#ptlig': 338, '#und': 66, '#orpes': 19}
        for k, v in expected.items():
            thisg = self.legacydoc.getroot().xpath('.//tei:g[@ref="%s"]' % k, namespaces=self.namespaces)
            self.assertEqual(len(thisg), v)

    def test_glyphs(self):
        """Need to make sure that the glyph elements present in the JSON
        transcription appear as glyph elements in the char_decl header, and
        appear correctly referenced as g elements in the text."""

        # input is <g ref="աշխարհ">աշխար</g>
        # output should be <g ref="#asxarh">աշխար</g>
        # another input is <g ref="">աշխարհ</g>

        test_input = [('#պտ', ''), ('աշխարհ', 'աշխար'), ('#asxarh', ''), ('', 'աշխարհ'), ('', 'ա'), ('', 'աշխարհ')]

        # check if 'char_decl' exists and is defined at the right place
        root = self.testdoc.getroot()
        tei_header = root.find("{{{:s}}}teiHeader".format(self.tei_ns))
        self.assertIsNotNone(tei_header)
        encoding_desc = tei_header.find("{{{:s}}}encodingDesc".format(self.tei_ns))
        self.assertIsNotNone(encoding_desc)
        char_decl = encoding_desc.find("{{{:s}}}charDecl".format(self.tei_ns))
        self.assertIsNotNone(char_decl)

        focused_tags = ['glyphName', 'mapping']
        file_tags = {"{{{:s}}}{:s}".format(self.tei_ns, tag): tag for tag in focused_tags}

        # for every test-tag check, if it is declaration
        char_decls = []
        for declaration in char_decl:
            self.assertEqual(declaration.tag, "{{{:s}}}glyph".format(self.tei_ns))
            charid = declaration.attrib.get(self.ns('id'))
            self.assertTrue(charid)

            values = {}
            for child in declaration:
                if child.tag in file_tags:
                    values[file_tags[child.tag]] = child.text

            # check, if the declaration contains a 'mapping' and 'glyphName' part
            for entry in focused_tags:
                self.assertTrue(values.get(entry))
            char_decls.append((charid, values['mapping']))

        # check if all tags from test_input are declared
        for tag in test_input:
            if tag[0]:
                key = tag[0][1:] if tag[0].startswith('#') else tag[0]
            else:
                key = tag[1]
            for decl in char_decls:
                if key in decl:
                    break
            else:
                self.assertTrue(False, 'Could not find declaration for tag <g ref="{0}">{1}</g>'.format(*tag))

    def test_linebreaks(self):
        """Need to make sure line breaks are added, while preserving any
        trailing space on the original transcription line. Also check that
        line xml:id is being calculated correctly."""

        # test results 'xml:id': ('n', 'trailing space)
        test_results = {"l101276867": ("1", False), "l101276826": ("1", False),
                        "l101276868": ("2", True), "l101276922": ("2", True),
                        "l101276869": ("3", True), "l101276923": ("3", False),
                        "l101276870": ("4", False), "l101276924": ("4", False),
                        "l101276871": ("5", False), "l101276925": ("5", False),
                        "l101276872": ("6", False), "l101276926": ("6", False),
                        "l101276873": ("7", True), "l101276834": ("7", True),
                        "l101276874": ("8", False), "l101276927": ("8", True),
                        "l101276875": ("9", True), "l101276928": ("9", False),
                        "l101276876": ("10", True), "l101276929": ("10", True),
                        "l101280110": ("11", True), "l101276930": ("11", True),
                        "l101276878": ("12", False), "l101276931": ("12", True),
                        "l101276879": ("13", False), "l101276840": ("13", False),
                        "l101276880": ("14", False), "l101276841": ("14", False),
                        "l101276881": ("15", True), "l101276932": ("15", True),
                        "l101276882": ("16", True), "l101276843": ("16", True),
                        "l101276883": ("17", True), "l101276933": ("17", False),
                        "l101276884": ("18", False), "l101276845": ("18", False),
                        "l101276885": ("19", False), "l101276934": ("19", False),
                        "l101276886": ("20", True), "l101276848": ("20", True),
                        "l101276887": ("21", False), "l101276935": ("21", True),
                        "l101276888": ("22", False), "l101276850": ("22", True),
                        "l101276889": ("23", True), "l101276936": ("23", False),
                        "l101276890": ("24", False), "l101276937": ("24", False),
                        "l101276891": ("25", False), "l101276853": ("25", False)}
        unchecked_lines = {key for key in test_results.keys()}

        for parent_element in self.testdoc.getroot().iterfind(".//{{{:s}}}ab".format(self.tei_ns)):
            line_id = None
            line_text = ""
            for element in parent_element:
                tag = element.tag
                if tag in [self.ns('pb'), self.ns('note')]:
                    line_id = None
                    line_text = ""
                    continue
                elif tag == self.ns('lb'):
                    n = element.attrib.get('n')
                    line_id = element.attrib.get(self.ns('id'))
                    self.assertTrue(line_id and line_id in test_results, 'Id not defined')
                    self.assertTrue(n, 'Number not defined')

                    # check that line xml:id is being calculated correctly.
                    self.assertEqual(n, test_results.get(line_id)[0], "Wrong Number/Id")

                if line_id and element.text:
                    line_text += element.text
                if line_id and element.tail:
                    line_text += element.tail

                if line_text.endswith("\n"):
                    self.assertTrue(line_id)

                    # check trailing spaces
                    if line_text.endswith(" \n"):
                        self.assertTrue(test_results.get(line_id)[1])
                    else:
                        self.assertFalse(test_results.get(line_id)[1])
                    unchecked_lines.discard(line_id)
                    line_text = ""
                    line_id = None

            self.assertEqual(0, len(unchecked_lines), "Test file seems incomplete!")
            break
        else:
            self.assertFalse(True, "No content found!")

    def test_members(self):
        msdata = helpers.load_JSON_file(self.testfiles['json'])
        testdoc = from_sc(
            msdata,
            members=helpers.test_members(),
            special_chars=self.glyphs
        )
        respstmt = testdoc.xpath('//tei:fileDesc/tei:editionStmt/tei:respStmt', namespaces=self.namespaces)
        self.assertEqual(1, len(respstmt))
        self.assertEqual('u281', respstmt[0].get(self.ns('id')))
        self.assertEqual('Me M. and I', respstmt[0].find(self.ns('name')).text)
        for line in testdoc.iter(self.ns('lb')):
            self.assertEquals('#u281', line.get('resp'))

    def test_metadata_included(self):
        """Check that the TPEN-supplied metadata ends up in the TEI header of the output."""

        # Check for correct TEI schema
        pis = self.testdoc.xpath('//processing-instruction()')
        self.assertEqual(len(pis), 1)
        for pi in pis:
            if pi.target is 'xml-model':
                self.assertEqual(pi.get('href'),
                                 'http://www.tei-c.org/release/xml/tei/custom/schema/relaxng/tei_all.rng')

        # Check for correct title
        titlestmt = self.testdoc.getroot().find(".//{%s}titleStmt" % self.tei_ns)
        for child in titlestmt:
            if child.tag is 'title':
                self.assertEqual(child.text, "M1731 (F) 1")

        # Check for correct MS description
        msdesc = self.testdoc.getroot().find(".//{%s}msDesc" % self.tei_ns)
        self.assertEqual(len(msdesc), 1)
        for child in msdesc:
            if child.tag is 'msIdentifier':
                self.assertEqual(child['{%s}id' % self.xml_ns], 'F')
                self.assertEqual(len(child), 3)
                for grandchild in child:
                    if grandchild.tag is 'settlement':
                        self.assertEqual(grandchild.text, "Yerevan")
                    if grandchild.tag is 'repository':
                        self.assertEqual(grandchild.text, "Matenadaran")
                    if grandchild.tag is 'idno':
                        self.assertEqual(grandchild.text, "1731")

    def test_metadata_passed(self):
        """Check that user-supplied metadata has its effect on the TEI header."""
        # Check for correct title
        titlestmt = self.legacydoc.getroot().find(".//{%s}titleStmt" % self.tei_ns)
        self.assertEqual(len(titlestmt), 2)
        for child in titlestmt:
            if child.tag is 'title':
                self.assertEqual(child.text, "Ժամանակագրութիւն")
            if child.tag is 'author':
                self.assertEqual(child.text, "Մատթէոս Ուռհայեցի")

        # Check for correct MS description
        msdesc = self.legacydoc.getroot().find(".//{%s}msDesc" % self.tei_ns)
        self.assertEqual(len(msdesc), 2)
        for child in msdesc:
            if child.tag is 'msIdentifier':
                self.assertEqual(child['{%s}id' % self.xml_ns], 'A')
                self.assertEqual(len(child), 3)
                for grandchild in child:
                    if grandchild.tag is 'settlement':
                        self.assertEqual(grandchild.text, "Yerevan")
                    if grandchild.tag is 'repository':
                        self.assertEqual(grandchild.text, "Matenadaran")
                    if grandchild.tag is 'idno':
                        self.assertEqual(grandchild.text, "1896")
            if child.tag is 'history':
                self.assertEqual(len(child), 2)
                for grandchild in child:
                    if grandchild.tag is 'origDate':
                        self.assertEqual(grandchild.text, "1689")
                    if grandchild.tag is 'origPlace':
                        self.assertEqual(grandchild.text, "Bitlis")

    def test_numbers(self):
        """Check that all the 'num' elements have well-defined values when we have used a number parser.
        Ideally this would check against the xsd: datatypes but I am not sure how to easily accomplish that."""
        for number in self.legacydoc.getroot().findall(".//{%s}num" % self.tei_ns):
            self.assertIn('value', number.keys())
            try:
                self.assertIsInstance(float(number.get('value')), float)
            except ValueError:
                self.fail()

    def test_parse_error(self):
        """Check that a reasonable error message is returned from a JSON file that
        contains badly-formed XML."""
        md = {'short_error': True}
        with io.StringIO() as buf, redirect_stderr(buf):
            badresult = from_sc(self.brokendata, md)
            errormsg = buf.getvalue()
        self.assertRegex(errormsg, 'Parsing error in the JSON')
        errorlines = errormsg.splitlines()[1:]
        self.assertEqual(len(errorlines), 55)
        self.assertRegex(errorlines[0], 'Affected portion of XML is 493: \<pb')

    def test_postprocess(self):
        d_json = helpers.load_JSON_file(self.testfiles['m3519'])
        d_root = from_sc(d_json,
                         special_chars=self.glyphs,
                         text_filter=helpers.tpen_filter,
                         postprocess=helpers.postprocess)
        visited = False
        for tag in d_root.iter(self.ns('pb')):
            visited = True
            self.assertEquals('interesting', tag.get('ana'))
        self.assertTrue(visited)