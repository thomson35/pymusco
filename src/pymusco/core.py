"""

https://automatetheboringstuff.com/chapter13/
https://github.com/RussellLuo/pdfbookmarker/blob/master/add_bookmarks.py
"""
import abc
# sudo port install py27-pypdf2
import PyPDF2
# from PyPDF2 import PdfFileMerger, PdfFileReader
from PIL import Image


# from wand.image import Image
import re


# from enum import Enum


class Instrument(object):

    def __init__(self, uid, player, order, is_rare=False):
        """
        :param str uid: unique identififer of a musical instrument, eg 'eb alto clarinet'
        :para float order: value that is used to order instruments
        """
        self.uid = uid
        self.player = player
        self.order = order
        self.is_rare = is_rare
        self.tone = None

    def get_id(self):
        return self.uid

    def get_player(self):
        """
        :return str: the type of musician that can play this instrument
        """
        return self.player

    def is_single(self):
        single_instruments = ['c piccolo',
                              'english horn',
                              'bb bass clarinet',
                              'eb clarinet',
                              'bb soprano saxophone',
                              'eb baritone saxophone',
                              'c bass trombone',
                              'piano',
                              'string bass',
                              'double bass']
        return self.uid in single_instruments


class Orchestra(object):
    
    def __init__(self, instruments):
        self.instruments = instruments

    def get_instrument(self, instrument_id):
        for instrument in self.instruments:
            if instrument.get_id() == instrument_id:
                return instrument
        assert False, 'unknown instrument id : %s' % instrument_id
        return None


"""
class Clef(Enum):
    TREBLE = 1
    BASS = 2
"""


class Track(object):
    
    def __init__(self, track_id, orchestra):
        """
        :param str track_id: the identifier of a track in the form "bb trombone 2 bc"
        :param Orchestra orchestra:
        """
        self.orchestra = orchestra
        self.instrument = None
        self.voice = None
        self.clef = None  # 'tc' for treble clef, 'bc' for bass clef
        self.is_solo = False
        self.is_disabled = False  # for tracks that we want to ignore (eg a track that is present in a stub more than once)
        parts = track_id.split(' ')
        instrument_first_part_index = 0
        instrument_last_part_index = len(parts) - 1
        # if len(parts[0]) <= 2:
        #    self.tone = parts[0]
        #   instrument_start_part_index = 1
        last_part = parts[-1]
        if last_part == 'disabled':
            self.is_disabled = True
            instrument_last_part_index -= 1
        last_part = parts[instrument_last_part_index]
        allowed_clefs = ['tc', 'bc']
        if last_part in allowed_clefs:
            self.clef = last_part
            instrument_last_part_index -= 1
        last_part = parts[instrument_last_part_index]
        if last_part.isdigit():
            self.voice = int(last_part)
            instrument_last_part_index -= 1
        last_part = parts[instrument_last_part_index]
        if last_part == 'solo':
            self.is_solo = True
            instrument_last_part_index -= 1
        instrument_id = ' '.join(parts[instrument_first_part_index:instrument_last_part_index + 1])
        self.instrument = orchestra.get_instrument(instrument_id)

    # def __init__(self, instrument, voice_number, clef):
    #    self.intrument = instrument
    #    self.voice_number = voice_number
    #    self.clef = clef
    
    def get_id(self):
        """
        :return str: the identifier of this track in the form "bb trombone 2 tc"
        """
        uid = self.instrument.get_id()
        if self.is_solo:
            uid = '%s solo' % uid
        if self.voice is not None:
            uid = '%s %d' % (uid, self.voice)
        if self.clef is not None:
            uid = '%s %s' % (uid, self.clef)
        if self.is_disabled:
            uid = '%s disabled' % uid
        return uid

    def __lt__(self, other):
        if self.instrument.order == other.instrument.order:
            if self.voice == other.voice:
                if self.clef == other.clef:
                    return False  # self and other are equal
                else:
                    if self.clef is None:
                        return True
                    elif other.clef is None:
                        return False
                    else:
                        return self.clef < other.clef
            else:
                if self.voice is None:
                    return True
                elif other.voice is None:
                    return False
                else:
                    return self.voice < other.voice
        else:
            return self.instrument.order < other.instrument.order

    @property
    def is_rare(self):
        if self.instrument.is_rare:
            return True
        else:
            if self.instrument.get_id() in ['c baritone horn', 'c bass']:
                if self.clef == 'tc':
                    # c basses are usually used by tubists, which on play bass clef
                    return True
            else:
                return False


def get_bookmarks_tree(bookmarks_filename):
    """Get bookmarks tree from TEXT-format file
    Bookmarks tree structure:
        >>> get_bookmarks_tree('sample_bookmarks.txt')
        [(u'Foreword', 0, []), (u'Chapter 1: Introduction', 1, [(u'1.1 Python', 1, [(u'1.1.1 Basic syntax', 1, []), (u'1.1.2 Hello world', 2, [])]), (u'1.2 Exercises', 3, [])]), (u'Chapter 2: Conclusion', 4, [])]
    The above test result may be more readable in the following format:
        [
            (u'Foreword', 0, []),
            (u'Chapter 1: Introduction', 1,
                [
                    (u'1.1 Python', 1,
                        [
                            (u'1.1.1 Basic syntax', 1, []),
                            (u'1.1.2 Hello world', 2, [])
                        ]
                    ),
                    (u'1.2 Exercises', 3, [])
                ]
            ),
            (u'Chapter 2: Conclusion', 4, [])
        ]
    Thanks Stefan, who share us a perfect solution for Python tree.
    See http://stackoverflow.com/questions/3009935/looking-for-a-good-python-tree-data-structure
    Since dictionary in Python is unordered, I use list instead now.
    Also thanks Caicono, who inspiring me that it's not a bad idea to record bookmark titles and page numbers by hand.
    See here: http://www.caicono.cn/wordpress/2010/01/%E6%80%9D%E8%80%83%E5%85%85%E5%88%86%E5%86%8D%E8%A1%8C%E5%8A%A8-python%E8%AF%95%E6%B0%B4%E8%AE%B0.html
    And I think it's the only solution for scan version PDFs to be processed automatically.
    """

    # bookmarks tree
    tree = []

    # the latest nodes (the old node will be replaced by a new one if they have the same level)
    #
    # each item (key, value) in dictionary represents a node
    # `key`: the level of the node
    # `value`: the children list of the node
    latest_nodes = {0: tree}

    prev_level = 0
    for line in codecs.open(bookmarks_filename, 'r', encoding='utf-8'):
        res = re.match(r'(\+*)\s*?"([^"]+)"\s*\|\s*(\d+)', line.strip())
        if res:
            pluses, title, pagenum = res.groups()
            cur_level = len(pluses)  # plus count stands for level
            cur_node = (title, int(pagenum) - 1, [])

            if not (cur_level > 0 and cur_level <= prev_level + 1):
                raise Exception('plus (+) count is invalid here: %s' % line.strip())
            else:
                # append the current node into its parent node (with the level `cur_level` - 1)
                latest_nodes[cur_level - 1].append(cur_node)

            latest_nodes[cur_level] = cur_node[2]
            prev_level = cur_level

    return tree


class TableOfContents(object):
    
    def __init__(self, label_to_page={}):
        """
        :param dict(str, int) label_to_page:
        """
        self.label_to_page = label_to_page
    
    def add_toc_item(self, label, page_index):
        """
        :param str label:
        :param int page_index:
        """
        self.label_to_page[label] = page_index
    
    def get_labels(self):
        return self.label_to_page.keys()
    
    def get_labels_for_page(self, page_index):
        labels = []
        for label, page in self.label_to_page.iteritems():
            if page == page_index:
                labels.append(label)
        return labels
    
    def get_tracks_first_page_index(self, tracks):
        """
        :param str tracks: slash separated tracks
        """
        return self.label_to_page[tracks.split('/')[0]]
    
    def get_tracks_last_page_index(self, tracks, num_pages):
        """
        :param str tracks: slash separated tracks
        """
        first_page_index = self.get_tracks_first_page_index(tracks)
        
        next_section_first_page_index = num_pages + 1
        for page_index in self.label_to_page.itervalues():
            if page_index > first_page_index:
                next_section_first_page_index = min(next_section_first_page_index, page_index)
        # assert next_section_first_page_index <= num_pages, 'next_section_first_page_index = %d, num_pages=%d' % (next_section_first_page_index, num_pages)
        return next_section_first_page_index - 1
    
    def shift_page_indices(self, offset):
        """
        shifts the page numbers by a fixed value
        
        useful to adjust page numbers when a page is inserted or deleted
        """
        for label in self.label_to_page.iterkeys():
            self.label_to_page[label] += offset

    # def copy(self, page_number_offset=0 ):
    #    toc = TableOfContents()
    #    return toc.


class ITrackSelector(object):
    """
    abstract class for the mechanism of track selection, which can vary.
    
    its main purpose is to compute for each track in the stub how many copies are wanted in the print
    """
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def get_track_to_copy(self, stub_tracks):
        """
        computes for each stub_track the number of prints to do
        
        :param list(str) stub_tracks:
        :return dict(str, int): the number of prints to do for each stub_track
        """
        raise NotImplementedError('this classe is incomplete (missing get_track_to_copy method)')


def rotate_image(image_path, degrees_to_rotate, saved_location):
    """

    Rotate the given photo the amount of given degreesk, show it and save it

    @param image_path: The path to the image to edit
    @param degrees_to_rotate: The number of degrees to rotate the image
    @param saved_location: Path to save the cropped image

    """
    image_obj = Image.open(image_path)
    rotated_image = image_obj.rotate(degrees_to_rotate, expand=True)
    rotated_image.save(saved_location)
    # rotated_image.show()

def get_stub_tracks(src_stub_file_path):
    """
    :param str src_stub_file_path:
    :return TableOfContents:
    """

    def get_pdf_toc_item_page_complicated(pdf_toc_item, pdf_reader):
        print('getting page number for table of contents item %s' % pdf_toc_item['/Title'])
        print('pdf_toc_item : %s' % pdf_toc_item)
        print('number of pages : ', len(list(pdf_reader.pages))) # Process all the objects.
        page_indirect_object = pdf_toc_item['/Page']
        page_indirect_object = pdf_toc_item.get('/Page')  # pdf_toc_item['/Page'] would return a PyPDF2.generic.DictionaryObject instead of PyPDF2.generic.IndirectObject, probably because it would dereference the IndirectObject. 

        #page_indirect_object = pdf_toc_item['/Page']
        #print('Page : ', page_indirect_object)
        # {'/Contents': IndirectObject(229, 0), '/Parent': IndirectObject(203, 0), '/Type': '/Page', '/Resources': IndirectObject(227, 0), '/MediaBox': [0, 0, 612, 792]}
        # print('Page/Contents : ', page_indirect_object['/Contents'])
        # print('Page/Resources : ', page_indirect_object['/Resources'])

        print(type(page_indirect_object))
        print('Page : ', page_indirect_object)

        for page_index in [2]:
            page = pdf_reader.pages[page_index]
            print('page ', page_index+1, ': ', page)
            print(type(page))
            print(type(page["/Contents"]))
            for k, v in page.iteritems():
                print(k, v)
                if k == '/Contents':
                    contents = v
                    print(type(contents))
                    if isinstance(contents, PyPDF2.generic.IndirectObject):
                        indirect_object = contents
                        print(indirect_object.idnum)

            # contents = page['/Contents']
            #contents = page.getContents()  # ['/Contents']
            #print(type(contents), repr(contents))
            #print(contents)
            # print('contents : %d\n', contents.idnum)
            # print('Annots: %d\n' % len(page['/Annots']))
            # reader.pages[0]: {'/Contents': IndirectObject(196, 0), '/Parent': IndirectObject(203, 0), '/Type': '/Page', '/Resources': IndirectObject(195, 0), '/MediaBox': [0, 0, 612, 792], '/Annots': [IndirectObject(171, 0), IndirectObject(172, 0), IndirectObject(173, 0), IndirectObject(174, 0), IndirectObject(175, 0), IndirectObject(176, 0), IndirectObject(177, 0), IndirectObject(178, 0), IndirectObject(179, 0), IndirectObject(180, 0), IndirectObject(181, 0), IndirectObject(182, 0), IndirectObject(183, 0), IndirectObject(184, 0), IndirectObject(185, 0), IndirectObject(186, 0), IndirectObject(187, 0), IndirectObject(188, 0), IndirectObject(189, 0), IndirectObject(190, 0), IndirectObject(191, 0), IndirectObject(192, 0), IndirectObject(193, 0)]}
            # reader.pages[2]: {'/Contents': IndirectObject(229, 0), '/Parent': IndirectObject(203, 0), '/Type': '/Page', '/Resources': IndirectObject(227, 0), '/MediaBox': [0, 0, 612, 792]}

            # print('page ', page+1, ' resolved: ', reader.resolvedObjects[page + 1])
        #for k, v in reader.resolvedObjects.iteritems():
        #    print(k, v['/Contents'])
        assert False

    def get_pdf_toc_item_page(pdf_toc_item, pdf_reader):
        print(pdf_reader)
        list(pdf_reader.pages)
        # print(pdf_reader.resolvedObjects)
        print('getting page number for table of contents item %s' % pdf_toc_item['/Title'])
        # print('pdf_toc_item : %s' % pdf_toc_item)  # {'/Title': u'c piccolo 1', '/Left': 155.354, '/Type': '/XYZ', '/Top': 669.191, '/Zoom': <PyPDF2.generic.NullObject object at 0x1194f1d50>, '/Page': IndirectObject(228, 0)}
        # print('number of pages : ', len(list(pdf_reader.pages))) # Process all the objects.
        # toc_item_page = pdf_toc_item['/Page']
        toc_item_page_indirect_obj = pdf_toc_item.get('/Page')  # pdf_toc_item['/Page'] would return a PyPDF2.generic.DictionaryObject instead of PyPDF2.generic.IndirectObject, probably because it would dereference the IndirectObject. 
        # print('toc_item_page : %s' % toc_item_page_indirect_obj)
        # print('idnum=%d' % toc_item_page_indirect_obj.idnum)
        object1 = pdf_reader.resolvedObjects[(0, toc_item_page_indirect_obj.idnum)]
        # print(type(object1))  # PyPDF2.generic.DictionaryObject
        # print(object1) # {'/Contents': IndirectObject(229, 0), '/Parent': IndirectObject(203, 0), '/Type': '/Page', '/Resources': IndirectObject(227, 0), '/MediaBox': [0, 0, 612, 792]}
        page_object_id = object1.get('/Contents').idnum
        print('looking for page with id %d' % page_object_id)
        for page_index in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_index]
            # print('page ', page_index+1, ': ', page)
            # print('page.getContents() : %s' % page.getContents().getObject())
            page_indirect_obj = page.get("/Contents")
            # print('page_indirect_obj : %s' % page_indirect_obj)
            # print('page_indirect_obj.getObject() : %s' % page_indirect_obj.getObject())
            
            if page_indirect_obj.idnum == page_object_id:
                print('found %s at page %d' % (pdf_toc_item['/Title'], page_index+1))
                return page_index + 1
            # assert False

        assert False

    with open(src_stub_file_path, 'rb') as stub_file:
        reader = PyPDF2.PdfFileReader(stub_file)
        toc = reader.outlines
        #print(toc)
        """
        [
            {'/Title': u'c piccolo', '/Left': 155.354, '/Type': '/XYZ', '/Top': 669.191, '/Zoom': <PyPDF2.generic.NullObject object at 0x1110b1a90>, '/Page': IndirectObject(29, 0)},
            {'/Title': u'c flute', '/Left': 155.354, '/Type': '/XYZ', '/Top': 669.191, '/Zoom': <PyPDF2.generic.NullObject object at 0x1110b1b10>, '/Page': IndirectObject(47, 0)}
        ]
        """


        stub_tracks = TableOfContents()
        for pdf_toc_item in toc:


            track_page_number = get_pdf_toc_item_page(pdf_toc_item, reader)
            # assert False, 'the implementation of this function is not finished yet'
            instruments = pdf_toc_item['/Title'].split('/')
            for instrument in instruments:
                stub_tracks.add_toc_item(instrument, track_page_number)

        return(stub_tracks)
