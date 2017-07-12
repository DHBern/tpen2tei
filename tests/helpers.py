import json


def load_JSON_file(filename, encoding = 'utf-8'):
    with open(filename, encoding=encoding) as testfile:
        return json.load(testfile)


def glyph_struct(glyphdict):
    """ Read in the YAML list of glyphs used in our test cases, and convert it
        to the tuple form understood by tpen2tei.
        The key is the normalized form; the tuple is (xml:id, description).
    """
    glyphs = {}
    for k, v in glyphdict.items():
        glyphs[k] = (v['glyphName'], v['mapping'])
    return glyphs


def armenian_numbers(val):
    """Given the text content of a <num> element, try to turn it into a number."""
    # Create the stack of characters
    sigfigs = [ord(c) for c in val.replace('և', '').upper() if 1328 < ord(c) < 1365]
    total = 0
    last = None
    for ch in sigfigs:
        # What is this one's numeric value?
        if ch < 1338:    # Ա-Թ
            chval = ch - 1328
        elif ch < 1347:  # Ժ-Ղ
            chval = (ch - 1337) * 10
        elif ch < 1356:  # Ճ-Ջ
            chval = (ch - 1346) * 100
        else:            # Ռ-Ք
            chval = (ch - 1355) * 1000

        # Put it in the total
        if last is None or chval < last:
            total += chval
        else:
            total *= chval
        last = chval
    return total


def tpen_filter(str):
    result = str.replace('_', '֊').replace('“', '"').replace('”', '"').replace(',', '.')
    return result